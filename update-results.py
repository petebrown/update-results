import requests
from bs4 import BeautifulSoup
import datetime as dt
import pandas as pd
from urllib.parse import urljoin
import asyncio
from playwright.async_api import async_playwright

async def fetch_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = await context.new_page()
        
        # Set extra HTTP headers
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        url = 'https://www.11v11.com/teams/tranmere-rovers/tab/matches/'
        await page.goto(url)
        
        # Get the page content (HTML)
        html_content = await page.content()
        
        await browser.close()

        return html_content

# url = 'https://www.11v11.com/teams/tranmere-rovers/tab/matches/'

# headers = {
#     'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
# }
# r = requests.get(url, headers = headers)

updates = []
# Find the date of the most recent game in the existing results dataframe
df = pd.read_csv('./data/results_df.csv', parse_dates=['game_date'])
max_date = df.game_date.max()
max_date = pd.Timestamp(max_date)

page_source = asyncio.run(fetch_html())

bs = BeautifulSoup(page_source, 'lxml')
season = bs.select_one('.seasonTitle').text.split(' ')[0].replace("-", "/")

games = bs.select('tbody tr')

for game in games:
    cols = game.select('td')
    
    date = cols[0].text.strip()
    date = dt.datetime.strptime(date, '%d %b %Y')

    teams = cols[1].text.strip()

    outcome = cols[2].text.strip()

    score = cols[3].text.strip()

    competition = cols[4].text.strip()

    if date <= max_date or outcome == '':
        next
    else:  
        team_names = teams.split(' v ')
        home_team = team_names[0]
        away_team = team_names[1]

        game_url = cols[1].select_one('a')['href']
        game_url = urljoin(url ,game_url)
        
        score = score.split(' ')
        final_score = score[0].split('-')
        home_goals = final_score[0]
        away_goals = final_score[1]

        try:
            secondary_score = score[1].replace('(', ' (').strip()
            secondary_score = secondary_score.replace("(", "").replace(")", "")
        except:
            secondary_score = ''

        if home_team == 'Tranmere Rovers':
            goals_for = home_goals
            goals_against = away_goals
            venue = 'H'
            opponent = away_team
        else:
            goals_for = away_goals
            goals_against = home_goals
            venue = 'A'
            opponent = home_team

        score = f'{goals_for}-{goals_against}'

        if competition == 'League Two':
            game_type = 'League'
            league_tier = 4
        elif competition == 'League Two Play-Offs':
            game_type = 'League Play-Off'
            league_tier = 4
        else:
            game_type = 'Cup'
            league_tier = ''

        r = requests.get(game_url, headers = headers)
        bs = BeautifulSoup(r.text, 'lxml')

        panel_rows = bs.select('.basicData tr')

        stadium = 'Unknown'
        attendance = ''

        for row in panel_rows:
            columns = row.select('td')

            column_title = columns[0].text.strip()
            if column_title == 'Venue':
                stadium = columns[1].text.strip()
            else:
                next
                
            if column_title == 'Attendance':
                attendance = columns[1].text.strip()
                attendance = attendance.replace(',', '')
                attendance = int(attendance)
            else:
                next

        game_record = {
            'season': season,
            'game_date': date,
            'opposition': opponent,
            'venue': venue,
            'score': score,
            'home_team': home_team,
            'away_team': away_team,
            'outcome': outcome,
            'home_goals': home_goals,
            'away_goals': away_goals,
            'secondary_score': secondary_score,
            'competition': competition,
            'goals_for': goals_for,
            'goals_against': goals_against,
            'source_url': game_url,
            'attendance': attendance,
            'stadium': stadium
        }
        updates.append(game_record)

if updates:
    updates_df = pd.DataFrame(updates)

    league_tier_map = {
        'National League': 5,
        'Football Conference Play-off': 5,
        'League Two': 4,
        'League Two Play-Offs': 4,
        'League One': 3,
        'League One Play-Offs': 3
    }
    updates_df['league_tier'] = updates_df.competition.map(league_tier_map)

    generic_comps_map = {
        "Football League Trophy": "Associate Members' Cup",
        "FA Cup": "FA Cup",
        "FA Trophy": "FA Trophy",
        "League One": "Football League",
        "League One Play-Offs": "Football League",
        "League Two": "Football League",
        "League Two Play-Offs": "Football League",
        "League Cup": "League Cup",
        "Football Conference Play-off": "Non-League",
        "National League": "Non-League"
    }
    updates_df['generic_comp'] = updates_df.competition.map(generic_comps_map)

    updates_df.loc[(updates_df.generic_comp.isin(["Football League", "Non-League"])), "game_type"] = "League"
    updates_df.loc[(updates_df.league_tier.isna()), "game_type"] = "Cup"
    updates_df.loc[(updates_df.competition.str.contains("Play-")), "game_type"] = "League Play-Off"
    
    def find_manager_on_date(input_date):
        input_date = pd.Timestamp(input_date)
        try:
            manager_index = managers_df.apply(lambda x : (input_date >= x.manager_start_date) & (input_date <= x.manager_end_date), axis = 1)
            manager = managers_df[manager_index].manager_name
            manager = manager.squeeze()
        except:
            manager = 'Unknown'
        return manager

    managers_df = pd.read_html("https://www.soccerbase.com/teams/team.sd?team_id=2598&teamTabs=managers")[1].rename(columns = {"Unnamed: 0": "manager_name", "FROM": "manager_start_date", "TO": "manager_end_date"})
    managers_df.manager_start_date = pd.to_datetime(managers_df.manager_start_date)
    managers_df.manager_end_date = managers_df.apply(lambda x: pd.to_datetime("today") if x.manager_end_date == "Present" else pd.to_datetime(x.manager_end_date), axis=1)

    updates_df['manager'] = updates_df.apply(lambda x : find_manager_on_date(x.game_date), axis = 1)
    updates_df[['home_goals', 'away_goals', 'goals_for', 'goals_against']] = updates_df[['home_goals', 'away_goals', 'goals_for', 'goals_against']].apply(lambda x: x.astype('string').astype('int64'))

    updates_df['goal_diff'] = updates_df.goals_for - updates_df.goals_against

    updates_df['goal_diff'] = updates_df['goal_diff'].astype('Int64')

    updates_df['ssn_game_no'] = 0
    updates_df['ssn_comp_game_no'] = 0

    updates_df['weekday'] = pd.to_datetime(updates_df.game_date).dt.day_name()

    updated_df = pd.concat([df, updates_df], ignore_index=True)
    updated_df['ssn_game_no'] = updated_df.sort_values(by=['game_date']).groupby(['season']).cumcount() + 1
    updated_df['ssn_comp_game_no'] = updated_df.sort_values(by=['game_date']).groupby(['season', 'competition']).cumcount() + 1

    updated_df = updated_df.sort_values(by=['game_date'], ascending=False)

    updated_df.to_csv('./data/results_df.csv', index=False)
else:
    print("No updates.")
