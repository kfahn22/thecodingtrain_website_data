import os
import unicodedata
import re
import requests
from bs4 import BeautifulSoup
from json import dumps, loads

def clean_text(text: str) -> str:
    """This converts the unicode characters to normalized Unicode form (i.e., something ASCII can handle."""
    return unicodedata.normalize('NFKD', text.strip()).encode('ascii', 'ignore').decode()

def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

def get_yt_pub_date(yt_id: str) -> str:
    # TODO: get thumbnail(s)?
    # TODO: get timestamps?
    url = f'https://www.youtube.com/watch?v={yt_id}'
    result = requests.get(url)
    src = result.content
    soup = BeautifulSoup(src, 'lxml')

    date_published = ''

    meta = soup.find_all('meta')

    for m in meta:
        if 'itemprop' in m.attrs:
            if m.attrs['itemprop'] == 'datePublished':
                date_published = m.attrs['content']
    
    return date_published

def get_code_actions(code_actions) -> dict:
    classes = code_actions['class']
    code_type = ''
    if classes[0] == 'p5js':
        code_type = 'p5'
    elif classes[0] == 'Processing':
        code_type = 'processing'
    else:
        raise ValueError(f'Unknown code type: {classes[0]}')
    
    code_actions_title = code_actions.find('span', {'class': 'title'}).text
    code_actions_ul = code_actions.find('ul')
    code_actions_li = code_actions_ul.find_all('li')

    code_examples = []
    for li in code_actions_li:
        a = li.find('a')
        href = a['href']
        text = a.text
        if text.lower() in ['web editor', 'view code']:
            if text.lower() == 'web editor':
                title = 'p5 Web Editor'
            else:
                if code_type == 'p5':
                    code_type = 'other'
                    title = 'GitHub'
                else:
                    title = 'Processing'
            urls = {}
            urls[code_type] = href
            code_examples.append({
                'title': f'{code_actions_title} - {title}',
                'description': '',
                'urls': urls
            })

    return code_examples

def process_contributions(contributions: list) -> list:
    contribs = []
    for li in contributions:
        title = ''
        proj_url = ''
        auth_name = ''
        auth_url = ''
        src_url = ''
        fake_link = li.find('span', {'class': 'fake-link'})
        if fake_link is not None:
            title = fake_link.text
            a = li.find_all('a')
            auth_a = li.find('i').find('a')
            if auth_a is not None:
                auth_name = auth_a.text
                auth_url = auth_a['href']
            else:
                auth_name = li.find('i').text
            if a[-1].text.lower() == 'source code':
                src_url = a[-1]['href']
        else:
            a = li.find_all('a')
            if len(a) == 3:
                title = a[0].text
                proj_url = a[0]['href']
                auth_name = a[1].text
                auth_url = a[1]['href']
                src_url = a[2]['href']
            elif len(a) in [1,2]:
                title = a[0].text
                proj_url = a[0]['href']
                if li.find('i').find('a') is not None:
                    auth_a = li.find('i').find('a')
                    auth_name = auth_a.text
                    auth_url = auth_a['href']
                else:
                    auth_name = li.find('i').text
                if a[-1].text.lower() == 'source code':
                    src_url = a[-1]['href']
            else:
                raise ValueError(f'Not able to handle contributions with {len(a)} anchor tags:\n{a}')
        contribs.append({
            'title': title,
            'url': proj_url,
            'author': {
                'name': auth_name,
                'url': auth_url
            },
            'source': src_url
        })
    return contribs


def get_challenge_data(url: str) -> dict:
    # get the page source and turn parse it with BeautifulSoup
    result = requests.get(url)
    src = result.content
    soup = BeautifulSoup(src, 'lxml')

    # get the "main" element - that's where the content is
    main = soup.find('main')
    
    # get the title
    title = main.find('h2').text
    
    # get the div where the YouTube video is
    # get the div with a class of "subtitle" to get the challenge number
    video = main.find('div', {'class': 'video'})
    subtitle = video.find('div', {'class': 'subtitle'}).text
    challenge_num = subtitle.split('#')[1].strip()
    
    # get the div with the actual video player
    player_and_topics = video.find('div', {'class': 'player-and-topics'})
    
    # get the "player" div
    player = player_and_topics.find('div', {'class': 'player'})
    # find the iframe with the YouTube video
    iframe = player.find('div', {'id': 'video-player'})
    # grab the video id from the iframe element's attributes
    video_id = iframe['data-videoid']
    
    # get the "topics" div and pull out the "p" element to get the video/challenge description
    topics = player_and_topics.find('div', {'class': 'topics'})
    topics_p = topics.find('p').text

    # get the "code-actions" div and determine whether we're dealing with p5 or Processing
    # TODO: need to make this a loop, actually, since there can be more than 1 p5 or Processing
    # section - this can happen if more than 1 example is made in the video: see challenge 166 (ASCII Image)
    code_examples = []
    code_actions = main.find('div', {'class': 'code-actions'})
    p5js = code_actions.find('div', {'class': 'p5js'})
    if p5js is not None:
        test = get_code_actions(p5js)
        code_examples.extend(test)
    processing = code_actions.find('div', {'class': 'Processing'})
    if processing is not None:
        test = get_code_actions(processing)
        code_examples.extend(test)

    # get the "links-and-books" div - this contains links to the Contributions, links discussed in video,
    # videos discussed in video, and/or other challenges mentioned sections
    links_and_books = main.find('div', {'class': 'links-and-books'})

    # grab out the "contributions" div and process them all into the contribs list
    contributions = links_and_books.find('div', {'class': 'contributions'})
    contribs = []
    if contributions is not None:
        list_items = contributions.find('ul').find_all('li')
        if len(list_items) > 0:
            contribs = process_contributions(list_items)
    
    # get a list of all of the "link-list" divs (this is where all of the other data is)
    link_lists = links_and_books.find_all('div', {'class': 'link-list'})
    group_links = []
    if len(link_lists) > 0:
        # loop over the lists and stuff their data into the group_links list
        for l in link_lists:
            h3 = l.find('h3').text
            # make sure we're not doing anything with the Contributions since we handle those separately/differently
            if h3.lower() != 'community contributions':
                link_type = ''
                if h3.lower().startswith('links'):
                    link_type = 'References'
                elif h3.lower().startswith('videos'):
                    link_type = 'Videos'
                elif h3.lower().startswith('community suggested'):
                    link_type = 'Community Suggested References'
                elif h3.lower().startswith('other parts of this coding challenge'):
                    link_type = 'Other Parts Of This Coding Challenge'
                else:
                    raise ValueError(f'Unknown link type: {h3}')
                data = {
                    'title': link_type,
                    'links': []
                }
                ul = l.find('ul')
                list_items = ul.find_all('li')
                for li in list_items:
                    a = li.find('a')
                    href = a['href']
                    text = a.text
                    data['links'].append({
                        'title': text,
                        'url': href,
                        'description': ''
                    })
                group_links.append(data)

    data = {
        'title': title,
        'description': topics_p,
        'videoNumber': challenge_num,
        'videoId': video_id,
        'date': get_yt_pub_date(video_id),
        'languages': [],
        'topics': [],
        'canContribute': True,
        'relatedChallenges': [],
        'timestamps': [],
        'codeExamples': code_examples,
        'groupLinks': group_links,
        'contributions': contribs
    }

    return data

def scrape_challenges() -> None:
    result = requests.get('https://thecodingtrain.com/CodingChallenges/')
    src = result.content
    soup = BeautifulSoup(src, 'lxml')

    videos = soup.find_all('div', {'class': 'video-card'})

    video_data = []
    for video in videos:
        href = video.find('a')['href']
        url = f'https://thecodingtrain.com{href}'
        data = get_challenge_data(url)
        video_data.append(data)
        print(url)
    
    with open('challenges.json', 'w') as f:
        f.write(dumps(video_data, indent=4, ensure_ascii=True))

def process_challenges():
    curr_dir = os.path.abspath(os.path.dirname(__file__))
    with open('challenges.json', 'r') as f:
        challenges = loads(f.read())
        for challenge in challenges:
            c = challenge
            contribs = challenge['contributions']
            del c['contributions']
            num = c['videoNumber'].strip()
            title = f'{num}-{slugify(c["title"].lower())}'
            folder = os.path.join(curr_dir, 'challenges', title)
            os.makedirs(folder,exist_ok=True)
            if len(contribs) > 0:
                showcase = os.path.join(folder, 'showcase')
                os.makedirs(showcase, exist_ok=True)
                for i, contrib in enumerate(contribs):
                    filename = os.path.join(showcase, f'contribution{i+1}.json')
                    with open(filename, 'w') as f:
                        f.write(dumps(contrib, ensure_ascii=True, indent=4))
                with open(os.path.join(folder, 'index.json'), 'w') as f:
                    f.write(dumps(c, ensure_ascii=True, indent=4))

if __name__ == '__main__':
    scrape_challenges()
    process_challenges()