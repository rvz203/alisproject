import logging
import requests
from urllib.parse import urljoin, urlparse  # To handle relative URLs and extract subdomains
from bs4 import BeautifulSoup
import jdatetime  # To handle Jalali (Persian) dates
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = '7534264544:AAE1dPVH4xUz9t6YDesNeeRlkTjNlYp13U4'

# Persian digits mapped to English digits
persian_digits = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
}

# Start command handler
async def start(update: Update, context):
    await update.message.reply_text('Hello! Send me a link and a word to search for across pages on that site.')

# Link message handler
async def handle_link(update: Update, context):
    global last_received_link
    message_text = update.message.text
    if 'http' in message_text:
        last_received_link = message_text
        await update.message.reply_text('Thanks for receiving the link! Now send me a word to search for on that page and its subsequent pages.')

# Word search handler
async def handle_word(update: Update, context):
    global last_received_link
    if not last_received_link:
        await update.message.reply_text('Please send a link first.')
        return

    word_to_search = update.message.text.strip()

    # Start checking the main page and its paginated pages
    await search_word_across_pages(update, context, word_to_search)

# Function to fetch and search for the word across multiple pages
async def search_word_across_pages(update: Update, context, word_to_search):
    global last_received_link
    next_page_url = last_received_link

    while next_page_url:
        try:
            response = requests.get(next_page_url)
            if response.status_code == 200:
                page_content = response.text
                soup = BeautifulSoup(page_content, 'html.parser')

                # Extract the main content container (modify the tag or class name if needed)
                main_content = soup.find_all(['article', 'div', 'p'])  # Adjust these tags based on the HTML structure

                found_word = False  # Flag to check if the word is found
                for section in main_content:
                    section_text = section.get_text().strip().lower()

                    # Log the content being searched (to debug what part of the page is being analyzed)
                    logging.info(f"Searching content: {section_text[:100]}")  # Print the first 100 characters for debugging

                    if word_to_search.lower() in section_text:
                        # Extract the date (modify the logic to match how the date is presented in the HTML)
                        post_date = extract_jalali_date(soup)  # Call extract_jalali_date on the full soup to ensure we're not missing the date
                        gregorian_date = convert_jalali_to_gregorian(post_date) if post_date else "Unknown Date"
                        
                        # Extract the subdomain
                        subdomain = extract_subdomain(next_page_url)

                        # Return the URL, subdomain, and date of the post
                        await update.message.reply_text(
                            f'The word "{word_to_search}" was found on this page: {next_page_url}\n'
                            f'Subdomain: {subdomain}\n'
                            f'Date: {gregorian_date}'
                        )
                        found_word = True
                        break

                if found_word:
                    return  # Stop after finding the word

                # Find the link for the next page (pagination using numbers)
                next_page_url = extract_next_page_url(soup, next_page_url)
                if not next_page_url:
                    await update.message.reply_text("Reached the last page. The word was not found.")
            else:
                await update.message.reply_text(f'Failed to fetch the page: {next_page_url}')
                next_page_url = None
        except Exception as e:
            await update.message.reply_text(f'An error occurred: {str(e)}')
            next_page_url = None

# Function to extract the subdomain from a URL
def extract_subdomain(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc  # This returns the full domain, including subdomain if present

# Helper function to extract the Jalali date from the page (Modify based on the exact HTML structure for the date)
def extract_jalali_date(soup):
    # Based on the provided image, the date is next to the clock icon. Adjust based on actual HTML structure.
    # Try to find the element with the Jalali date.
    
    date_element = soup.find('span', class_='post-date')  # Adjust 'post-date' based on your site's actual class structure

    # If the date element is found, return the date text
    if date_element:
        date_text = date_element.get_text().strip()
        logging.info(f"Extracted Jalali Date: {date_text}")  # Log the extracted Jalali date for debugging
        return date_text

    return None

# Helper function to extract the URL for the next page in pagination (using numbered pagination)
def extract_next_page_url(soup, current_url):
    # Find the current active page and get the link to the next numbered page
    current_page = soup.find('a', class_='active')  # Assuming active page has the class 'active', adjust if needed
    if current_page:
        next_page = current_page.find_next('a')  # Find the next <a> element
        if next_page and next_page.has_attr('href'):
            relative_url = next_page['href']
            # Convert relative URL to absolute URL
            absolute_url = urljoin(current_url, relative_url)
            return absolute_url
    return None

# Function to convert Jalali date to Gregorian date
def convert_jalali_to_gregorian(jalali_date_str):
    if not jalali_date_str:
        return "Unknown Date"
    
    # Convert Persian digits to Western digits
    jalali_date_str = convert_persian_digits(jalali_date_str)

    # Split the string by '/' to handle "YYYY/MM/DD"
    parts = jalali_date_str.split('/')
    if len(parts) == 3:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

        # Convert Jalali date to Gregorian using jdatetime
        jalali_date = jdatetime.date(year, month, day)
        gregorian_date = jalali_date.togregorian()

        return gregorian_date
    else:
        return "Unknown Date"

# Function to replace Persian digits with Western digits
def convert_persian_digits(persian_str):
    return ''.join([persian_digits.get(c, c) for c in persian_str])

# Main function to run the bot
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Entity("url"), handle_link))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.Entity("url"), handle_word))

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
