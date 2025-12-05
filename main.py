from database import create_tables
from crawler import LeetCodeCrawler
from renderer import render_anki

# create database
create_tables()

# start crawler with parallel processing (default: 5 workers)
# Increase max_workers for faster processing (e.g., 10), but be careful not to trigger rate limits
worker = LeetCodeCrawler(max_workers=8)
worker.login()
worker.fetch_accepted_problems()

# render anki
render_anki()