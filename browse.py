import time
import os
from playwright.sync_api import sync_playwright, expect
import sys, multiprocessing
import os
import json
import requests
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QTextEdit, QSizePolicy, QPushButton, QScrollArea)
from PyQt5.QtGui import QFont, QIcon, QCursor, QPixmap, QColor
from PyQt5.QtCore import Qt, QSize

class TweetFrame(QFrame):
    def __init__(self, text, is_original=False, parent=None):
        super().__init__(parent)
        self.setObjectName("tweetFrame")
        layout = QVBoxLayout()

        # Tweet text
        self.tweet_text = QTextEdit(text)
        self.tweet_text.setReadOnly(True)
        self.tweet_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tweet_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tweet_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tweet_text.setStyleSheet(f"color: #000000; font-size: 16px; background-color: transparent; border: none;")

        layout.addWidget(self.tweet_text)

        self.setLayout(layout)
        self.setStyleSheet(f"""
            QFrame#tweetFrame {{
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                padding: 10px;
                margin-bottom: 10px;
            }}
        """)

    def sizeHint(self):
        return self.tweet_text.document().size().toSize() + QSize(20, 20)

class TweetResponder(QWidget):
    def __init__(self, original_post, reply, suggestions, page):
        super().__init__()
        self.reply = reply
        self.original_post = original_post
        self.suggestions = suggestions
        self.page = page
        self.setWindowTitle("Tweet and Suggestions")
        self.resize(800, 1000)
        self.setWindowIcon(QIcon('icon.png'))
        self.setStyleSheet("""
            QWidget {
                background-color: #F5F8FA;
                color: #14171A;
                font-family: "Helvetica Neue", Arial, sans-serif;
            }
            QLabel {
                color: #14171A;
            }
            QPushButton {
                background-color: #1DA1F2;
                color: #FFFFFF;
                border: none;
                border-radius: 20px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1A91DA;
            }
        """)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Original Tweet Display
        scroll_layout.addWidget(QLabel("Original Tweet:"))
        self.tweet_frame = TweetFrame(self.original_post, is_original=True)
        scroll_layout.addWidget(self.tweet_frame)

        # Reply Display
        scroll_layout.addWidget(QLabel("Reply:"))
        if self.reply != "no replies":
            self.reply_frame = TweetFrame(self.reply)
            scroll_layout.addWidget(self.reply_frame)
        else:
            no_reply_label = QLabel("No replies yet")
            no_reply_label.setStyleSheet("font-style: italic;")
            scroll_layout.addWidget(no_reply_label)

        # Suggestions Display
        if self.suggestions:
            scroll_layout.addWidget(QLabel("Suggested Replies:"))
            for suggestion in self.suggestions:
                suggestion_frame = QFrame()
                suggestion_layout = QVBoxLayout(suggestion_frame)

                suggestion_text = QTextEdit(suggestion)
                suggestion_text.setReadOnly(True)
                suggestion_layout.addWidget(suggestion_text)

                use_reply_button = QPushButton("Use This Reply")
                use_reply_button.clicked.connect(lambda _, s=suggestion: self.use_reply(s))
                suggestion_layout.addWidget(use_reply_button)

                scroll_layout.addWidget(suggestion_frame)

        # No Response Button
        no_response_button = QPushButton("No Response")
        no_response_button.clicked.connect(self.no_response)
        scroll_layout.addWidget(no_response_button)

        scroll_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def use_reply(self, suggestion):
        try:
            # Find all reply buttons
            reply_buttons = self.page.query_selector_all('button[data-testid="reply"]')

            if len(reply_buttons) < 2:
                raise Exception("Couldn't find the reply button for the comment")

            # Click the second reply button (first one is for the original tweet, second is for the comment)
            reply_buttons[1].click()

            # Wait for the reply text box to appear and type the suggestion
            self.page.wait_for_selector('div[data-testid="tweetTextarea_0"]')

            # Use the correct selector to fill in the suggestion
            textarea_selector = 'div[data-testid="tweetTextarea_0"] div[contenteditable="true"]'
            self.page.wait_for_selector(textarea_selector)
            self.page.fill(textarea_selector, suggestion)

            # Click the Reply button
            self.page.click('div[data-testid="tweetButtonInline"]')

            QMessageBox.information(self, "Reply Sent", "Your reply has been posted successfully!")
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to post reply: {str(e)}")

    def no_response(self):
        QMessageBox.information(self, "No Response", "You have chosen not to respond.")
        self.close()

CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'  # Example Claude API URL
API_KEY = os.getenv('CLAUDE_API_KEY')
headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'anthropic-version': '2023-06-01'  # Replace with the correct version
}

def generate_claude_replies(prompt):
    """Calls Claude API to generate replies based on the prompt."""
    payload = {
        'model': 'claude-3-5-sonnet-20240620',
        'max_tokens': 1024,
        'messages': [
            {
                'role': 'user',
                'content': f"{prompt}\n\nPlease provide 3 distinct reply suggestions, each on a new line."
            }
        ]
    }
    try:
        response = requests.post(CLAUDE_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        result = response.json()
        content = result.get('content', [])
        if content and isinstance(content[0], dict):
            text = content[0].get('text', '')
            suggestions = [line.strip() for line in text.split('\n') if line.strip()]
            return suggestions[:3]
        else:
            print("Unexpected response structure:", result)
            return []
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        if response:
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

def login_x(page):
    print("Navigating to login page...")
    page.goto("https://x.com/login", wait_until="networkidle")
    print("Page loaded.")

    # Wait for and fill in the username
    username_selector = 'input[name="text"]'
    print("Waiting for username input...")
    page.wait_for_selector(username_selector, state='visible', timeout=60000)
    print("Filling username...")
    page.fill(username_selector, USERNAME)

    # Press Enter instead of clicking "Next"
    print("Pressing Enter after username...")
    page.press(username_selector, 'Enter')

    # Wait for and fill in the password
    password_selector = 'input[name="password"]'
    print("Waiting for password input...")
    page.wait_for_selector(password_selector, state='visible', timeout=60000)
    print("Filling password...")
    page.fill(password_selector, PASSWORD)

    # Press Enter to log in instead of clicking the button
    print("Pressing Enter to log in...")
    page.press(password_selector, 'Enter')

    # Wait for navigation to complete
    print("Waiting for navigation to complete...")

    page.wait_for_timeout(5000)  # Additional wait to ensure everything is loaded

def get_most_recent_tweet_and_reply(page):
    print(f"Navigating to {USERNAME}'s profile...")
    page.goto(f"https://x.com/{USERNAME}")

    print("Scrolling to load more tweets...")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)  # Wait for content to load

    print("Locating the most recent tweet...")
    tweet_selector = 'article[data-testid="tweet"]'
    page.wait_for_selector(tweet_selector)
    tweets = page.query_selector_all(tweet_selector)
    print(tweets if tweets else "NO TWEETS LOCATED BRUH")
    if tweets:
        most_recent_tweet = tweets[0]
        print("Clicking on the most recent tweet...")
        most_recent_tweet.click()

        page.wait_for_timeout(2000)  # Wait for content to load

        print("Extracting post URL...")
        post_url = page.url

        print("Extracting original post...")
        original_post = page.query_selector('div[data-testid="tweetText"]')
        original_post_text = original_post.inner_text() if original_post else "No original post found"

        print("Checking for replies...")
        replies = page.query_selector_all('div[data-testid="cellInnerDiv"] article')

        if len(replies) > 1:
            reply_text = replies[1].query_selector('div[data-testid="tweetText"]').inner_text()
            print("Reply found.")
        else:
            reply_text = "no replies"
            print("No replies found.")

        return post_url, original_post_text, reply_text
    else:
        print("No tweets found")
        return None, None, None

def save_to_file(content, filename):
    downloads_folder = os.path.expanduser("~/Downloads")
    file_path = os.path.join(downloads_folder, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    print(f"Saved to {file_path}")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        page.set_default_timeout(60000)  # Set default timeout to 60 seconds

        try:
            login_x(page)
            # Save a screenshot for debugging
            page.screenshot(path="after_login.png")

            # Retrieve most recent tweet URL, original post, and reply
            post_url, original_post, reply = get_most_recent_tweet_and_reply(page)

            if post_url and original_post:
                print(f"Most recent tweet URL: {post_url}")
                print(f"Original tweet: {original_post}")
                print(f"Reply: {reply}")

                prompt = f"Original Tweet: {original_post}\nDraft a polite and engaging unique and clever response."
                suggestions = generate_claude_replies(prompt)
                print("Generated suggestions:", suggestions)

                if not suggestions:
                    print("No suggestions were generated. Proceeding with empty list.")

                app = QApplication(sys.argv)
                window = TweetResponder(original_post, reply, suggestions, page)
                window.show()
                sys.exit(app.exec_())
            else:
                print("Couldn't retrieve the tweet or URL.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            # Save a screenshot when an error occurs
            page.screenshot(path="error_screenshot.png")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
