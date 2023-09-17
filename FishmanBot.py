import requests
import datetime
from bs4 import BeautifulSoup
import time
import telegram.ext
from telegram.ext import Application, CommandHandler
from datetime import timedelta
import json


bot = telegram.Bot(token="BOT_TOKEN")

# Load team URLs and user IDs from the saved file
try:
    with open('team_urls.json', 'r') as f:
        team_urls = json.load(f)
except FileNotFoundError:
    # The file doesn't exist, so we'll create it later when we save the dictionary
    team_urls = {}


# define a function to check if the user is an admin
async def is_admin(update, context):
    if update.effective_chat.type == 'private':
       return True
    user = update.effective_user
    chat_id = update.effective_chat.id
    chat_admins = await context.bot.get_chat_administrators(chat_id)
    admin_ids = [admin.user.id for admin in chat_admins]
    return user.id in admin_ids


def search_team(team_name):
    """Search for the team URL on dltv.org"""
    # Convert the team name to a valid search query by replacing spaces with %20
    team_query = team_name.replace(' ', '%20')
    url = f"https://dltv.org/search/teams?q={team_query}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    try:
        team_url = soup.select_one(".search__results-case__item")["href"]
    except:
        return None
    return team_url


async def start(update, context):
    if await is_admin(update, context):
        """Start the bot"""
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Привет! Я бот, который будет уведомлять тебя о матчах любимых Dota 2 "
                                      "команд.\nНачни взаимодействие со мной с /help!")


async def help_bot(update, context):
    if await is_admin(update, context):
        """Display help text"""
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='''Отправь мне "/follow [ссылка на страницу твоей любимой команды на портале dltv.org ]".\nВАЖНО: ссылка должна быть с англоязычной версии портала!!!\nЯ буду уведомлять тебя о приближающихся матчах.\nВозможности:\n/follow [ссылка] - подписаться на команду\n/unfollow [ссылка] - отписаться от команды\n/next [ссылка] - информация о следующем матче команды\n/list - список подписок''')


def save_followed_teams():
    """Save the followed teams to the file"""
    with open("team_urls.json", "w") as file:
        json.dump(team_urls, file)


async def follow(update, context):
    """Save the team URL and user ID"""
    if await is_admin(update, context):
        # Get the user ID and the URL from the message text
        user_id = update.effective_chat.id
        try:
            input_text = update.message.text.strip().split(' ', 1)[1]
        except IndexError:
            context.bot.send_message(chat_id=user_id, text="Пожалуйста, укажи URL.")
            return

        # Check if the input is a valid URL
        if input_text.startswith("https://dltv.org/teams/"):
            team_url = input_text
        else:
            # Search for the team URL using the team name
            team_url = search_team(input_text)
            if team_url is None:
                await context.bot.send_message(chat_id=user_id, text="Введён неверный URL или название команды.")
                return

        # Check if the user is already following the team
        if team_url in team_urls and user_id in team_urls[team_url]:
            await context.bot.send_message(chat_id=user_id, text="Ты уже подписан на эту команду.")
            return

        # Append the user ID to the list of users associated with the URL in the dictionary
        if team_url in team_urls:
            if isinstance(team_urls[team_url], list):
                team_urls[team_url].append(user_id)
            else:
                team_urls[team_url] = [team_urls[team_url], user_id]
        else:
            team_urls[team_url] = [user_id]

        await context.bot.send_message(chat_id=user_id, text="Успешно! Теперь ты подписан на " + team_url + "!", disable_web_page_preview=True)
        save_followed_teams()


async def unfollow(update, context):
    """Remove the user ID from the list associated with the team URL"""
    if await is_admin(update, context):
        # Get the user ID and the URL from the message text
        user_id = update.effective_chat.id
        try:
            input_text = update.message.text.strip().split(' ', 1)[1]
        except IndexError:
            await context.bot.send_message(chat_id=user_id, text="Пожалуйста, укажи URL.")
            return

        # Check if the input is a valid URL
        if input_text.startswith("https://dltv.org/teams/"):
            team_url = input_text
        else:
            # Search for the team URL using the team name
            team_url = search_team(input_text)
            if team_url is None:
                await context.bot.send_message(chat_id=user_id, text="Введён неверный URL или название команды.")
                return

        # Remove the user ID from the list of users associated with the URL in the dictionary
        if team_url not in team_urls or user_id not in team_urls[team_url]:
            await context.bot.send_message(chat_id=user_id, text="Ты не был подписан на эту команду.")
        else:
            team_urls[team_url].remove(user_id)
            await context.bot.send_message(chat_id=user_id, text=f"Ты успешно отписался от {team_url}.",
                                     disable_web_page_preview=True)
            # If there are no user IDs attached to the URL, delete it from the dictionary
            if not team_urls[team_url]:
                del team_urls[team_url]

        save_followed_teams()


async def list_url(update, context):
    """Handler for the /list command"""
    chat_id = update.effective_chat.id

    if await is_admin(update, context):
        # Get the list of followed teams for the chat
        teams_followed = [url for url, users in team_urls.items() if chat_id in users]

        if teams_followed:
            message = f"Ты подписан на следующие команды:\n"
            for team_url in teams_followed:
                message += f"{team_url}\n"
        else:
            message = "Ты ещё ни на кого не подписался! Начни взаимодействие со мной с /help!"

        await context.bot.send_message(chat_id=chat_id, text=message, disable_web_page_preview=True)


async def next_match(update, context):
    """Handler for the /next_match command"""
    user_id = update.effective_chat.id

    if await is_admin(update, context):
        # Get the team URL from the message text
        try:
            input_text = update.message.text.strip().split(' ', 1)[1]
        except IndexError:
            await context.bot.send_message(chat_id=user_id, text="Пожалуйста, укажи URL.")
            return

        # Check if the input is a valid URL
        if input_text.startswith("https://dltv.org/teams/"):
            team_url = input_text
        else:
            # Search for the team URL using the team name
            team_url = search_team(input_text)
            if team_url is None:
                await context.bot.send_message(chat_id=user_id, text="Введён неверный URL или название команды.")
                return
            time.sleep(5)

        # Send a GET request to the team page
        page = requests.get(team_url)

        # Parse the HTML content of the page
        soup = BeautifulSoup(page.content, "html.parser")

        # Find the element that contains the time until the next game
        next_game = soup.select_one("[data-match-timer]")

        if next_game:
            # Convert the time of the next game to a timedelta object
            time_until_next_game = datetime.timedelta(seconds=int(next_game.get_text()))

            # Get the current time
            current_time = datetime.datetime.now()

            # Calculate the time of the next game
            next_game_time = current_time + time_until_next_game

            # Format the time of the next game as a string
            next_game_time_str = next_game_time.strftime("%d.%m.%Y %H:%M")

            ally_team = soup.find("h1").text

            # Find the tournament name for the next game
            tournament_name = soup.find("a", class_="event-card-event overflow-text-1").text

            # Find the match link
            match_link = soup.find("a", class_="event-card-match")["href"]

            match_page = requests.get(match_link)

            # Scrape the match page using the match link
            soup_match = BeautifulSoup(match_page.content, "html.parser")

            team_elements = soup_match.find_all('div', class_='team')

            try:
                for team_element in team_elements:
                    if ally_team == team_element.find('a', class_='team__stats-name').text.strip():
                        continue
                    enemy_team = team_element.find('a', class_='team__stats-name').text.strip()
                    break
            except:
                await context.bot.send_message(chat_id=user_id, text="У данной команды запланирован матч на " + tournament_name + " в " + next_game_time_str + " (UTC+3), но соперник ещё не известен!")

            # Send the time of the next game to the user
            await context.bot.send_message(chat_id=user_id, text=f"Следующая игра <b>{ally_team}</b> на {tournament_name} пройдёт <b>{next_game_time_str}</b> (UTC+3) против <b>{enemy_team}</b>!\n\n<a href='{match_link}'>Match Page</a>", disable_web_page_preview=True, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=user_id, text="Для указанной команды пока что нет ближайших матчей.")


async def check_game_time(context):
    """Check the next game time for each team"""
    for team_url, user_ids in dict(team_urls).items():
        # Send a GET request to the team page
        page = requests.get(team_url)
        # Parse the HTML content of the page
        soup = BeautifulSoup(page.content, "html.parser")
        next_game = soup.select_one("[data-match-timer]")

        if next_game:

            # Convert the time of the next game to a datetime object
            time_until_next_game = datetime.timedelta(seconds=int(next_game.get_text()))

            ally_team = soup.find("h1").text

            # Find the tournament name for the next game
            tournament_name = soup.find("a", class_="event-card-event overflow-text-1").text

            # Find the match link
            match_link = soup.find("a", class_="event-card-match")["href"]

            match_page = requests.get(match_link)

            # Scrape the match page using the match link
            soup_match = BeautifulSoup(match_page.content, "html.parser")

            team_elements = soup_match.find_all('div', class_='team')

            for team_element in team_elements:
                if ally_team == team_element.find('a', class_='team__stats-name').text.strip():
                    continue
                enemy_team = team_element.find('a', class_='team__stats-name').text.strip()
                break

            # Find the stream with the most viewers
            stream = soup_match.find("div", class_="swiper-slide")
            if stream is not None:
                stream_link = stream.find("a").get("href")
                channel_name = stream_link.split("/")[-2]
                short_link = "https://www.twitch.tv/" + channel_name
            else:
                short_link = "***"

            if timedelta(minutes=10) <= time_until_next_game <= timedelta(minutes=11):
                for user_id in user_ids:
                    # Send the notification to the chat
                    await bot.send_message(chat_id=int(user_id), text="До следующей игры <b>" + ally_team + "</b> на " + tournament_name + " осталось <b>10 минут!</b>\nЗаходите поддержать парней в матче против <b>" + enemy_team + "</b>:\n" + str(short_link)+ "\n\n<a href=\"" + match_link + "\">Match Page</a>", disable_web_page_preview=True, parse_mode='HTML')
        else:
            time.sleep(5)

async def last_match(update, context):
    if await is_admin(update, context):
        # Get the user ID and the URL from the message text
        user_id = update.effective_chat.id
        try:
            input_text = update.message.text.strip().split(' ', 1)[1]
        except IndexError:
            await context.bot.send_message(chat_id=user_id, text="Пожалуйста, укажи URL.")
            return

        # Check if the input is a valid URL
        if input_text.startswith("https://dltv.org/teams/"):
            team_url = input_text
        else:
            # Search for the team URL using the team name
            team_url = search_team(input_text)
            if team_url is None:
                await context.bot.send_message(chat_id=user_id, text="Введён неверный URL или название команды.")
                return
            team_url += "/matches"

        # Send a GET request to the team's matches page
        response = requests.get(team_url)

        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, "html.parser")

        # Find the last match element
        last_match = soup.find("div", class_="table__body-row")

        if last_match:
            # Extract the team names and scores from the match element
            team_elements = last_match.find_all("div", class_="team")
            team1_name = team_elements[0].find("div", class_="cell__name").text.strip()
            team2_name = team_elements[1].find("div", class_="cell__name").text.strip()
            score_elements = last_match.find("div", class_="score").find_all("span")
            team1_score = score_elements[0].text.strip()
            team2_score = score_elements[1].text.strip()

            # Return the score of the last match
            await context.bot.send_message(chat_id=user_id, text=f"{team1_name} {team1_score} - {team2_score} {team2_name}")
        else:
            await context.bot.send_message(chat_id=user_id, text="Не найдено предыдущих матчей для этой команды")


def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token("BOT_TOKEN").build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_bot))
    application.add_handler(CommandHandler("follow", follow))
    application.add_handler(CommandHandler("unfollow", unfollow))
    application.add_handler(CommandHandler("list", list_url))
    application.add_handler(CommandHandler("next", next_match))
    application.add_handler(CommandHandler("last", last_match))
    job_queue = application.job_queue

    job_minute = job_queue.run_repeating(check_game_time, interval=60, first=5)

    application.run_polling()


# Run the bot
if __name__ == '__main__':
    main()

