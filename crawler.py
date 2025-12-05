import json
import os.path
import pickle
import re
from sys import exit
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
from requests.cookies import RequestsCookieJar
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from database import Problem, ProblemTag, Tag, Submission, create_tables, Solution
from utils import destructure, random_wait, do, get

COOKIE_PATH = "./cookies.dat"


class LeetCodeCrawler:
    def __init__(self, max_workers=5):
        # create an http session
        self.session = requests.Session()
        self.browser = webdriver.Edge()
        self.max_workers = max_workers
        self.lock = threading.Lock()  # for thread-safe database operations
        self.session.headers.update(
            {
                'Host': 'leetcode.com',
                'Cache-Control': 'max-age=0',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://leetcode.com/accounts/login/',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.8,en;q=0.6',
                'Connection': 'keep-alive'
            }
        )

    def login(self):
        print("[*] Starting browser login..., please fill the login form")
        print("[*] You have 1 minute to log in to your LeetCode account")
        try:
            # browser login
            login_url = "https://leetcode.com/accounts/login"
            self.browser.get(login_url)

            # Wait up to 1 minute (60 seconds) for login to complete
            # Check if the URL changes (no longer contains "login")
            WebDriverWait(self.browser, 60).until(
                lambda driver: "login" not in driver.current_url.lower()
            )
            print("[+] Login detected! Waiting 30 seconds for session to stabilize...")
            import time
            time.sleep(30)  # Wait 30 seconds for cookies and session to be fully established
            
            browser_cookies = self.browser.get_cookies()
            print(f"[+] Login successfully, obtained {len(browser_cookies)} cookies")

        except Exception as e:
            print(f"[-] Login Failed: {e}, please try again")
            exit()

        cookies = RequestsCookieJar()
        csrf_token = None
        for item in browser_cookies:
            cookies.set(item['name'], item['value'])

            if item['name'] == 'csrftoken':
                csrf_token = item['value']
                self.session.headers.update({
                    "x-csrftoken": item['value']
                })

        self.session.cookies.update(cookies)
        
        # Verify authentication by checking if we can access /api/problems/all/
        print("[*] Verifying authentication...")
        try:
            response = self.session.get("https://leetcode.com/api/problems/all/")
            if response.status_code == 200:
                data = json.loads(response.content.decode('utf-8'))
                if 'stat_status_pairs' in data:
                    print(f"[+] Authentication verified! Found {len(data['stat_status_pairs'])} problems")
                else:
                    print("[-] Authentication failed: Invalid response format")
                    print(f"[-] Response keys: {list(data.keys())}")
            else:
                print(f"[-] Authentication failed: Status code {response.status_code}")
                print(f"[-] Response: {response.text[:200]}")
        except Exception as e:
            print(f"[-] Error verifying authentication: {e}")


    def _process_problem(self, slug, is_new):
        """Process a single problem: fetch problem, solution, and submission"""
        try:
            if is_new:
                # fetch problem and solution for new problems
                do(self.fetch_problem, args=[slug, True])
                do(self.fetch_solution, args=[slug])
            
            # always try to update submission
            do(self.fetch_submission, args=[slug])
            return True, slug, is_new
        except Exception as e:
            print(f"[!] Error processing {slug}: {e}")
            return False, slug, is_new

    def fetch_accepted_problems(self):
        response = self.session.get("https://leetcode.com/api/problems/all/")
        all_problems = json.loads(response.content.decode('utf-8'))
        
        # Prepare list of problems to process
        problems_to_process = []
        total_ac = 0
        
        for item in all_problems['stat_status_pairs']:
            if item['status'] == 'ac':
                total_ac += 1
                id, slug = destructure(item['stat'], "question_id", "question__title_slug")
                is_new = Problem.get_or_none(Problem.id == id) is None
                problems_to_process.append((slug, is_new))
        
        print(f"[*] Total AC problems: {total_ac}")
        print(f"[*] Processing {len(problems_to_process)} problems with {self.max_workers} workers...")
        
        # Process problems in parallel
        new_problems = 0
        existing_problems = 0
        successful = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_problem = {executor.submit(self._process_problem, slug, is_new): (slug, is_new) 
                                for slug, is_new in problems_to_process}
            
            # Process completed tasks
            for future in as_completed(future_to_problem):
                slug, is_new = future_to_problem[future]
                try:
                    success, _, was_new = future.result()
                    if success:
                        successful += 1
                        if was_new:
                            new_problems += 1
                        else:
                            existing_problems += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[!] Exception for {slug}: {e}")
                    failed += 1
        
        print(f"[*] New problems added: {new_problems}")
        print(f"[*] Existing problems (submissions updated): {existing_problems}")
        print(f"[*] Successful: {successful}, Failed: {failed}")

    def fetch_problem(self, slug, accepted=False):
        print(f"[*] Fetching problem: https://leetcode.com/problem/{slug}/...")
        query_params = {
            'operationName': "getQuestionDetail",
            'variables': {'titleSlug': slug},
            'query': '''query getQuestionDetail($titleSlug: String!) {
                        question(titleSlug: $titleSlug) {
                            questionId
                            questionFrontendId
                            questionTitle
                            questionTitleSlug
                            content
                            difficulty
                            stats
                            similarQuestions
                            categoryTitle
                            topicTags {
                            name
                            slug
                        }
                    }
                }'''
        }

        resp = self.session.post(
            "https://leetcode.com/graphql",
            data=json.dumps(query_params).encode('utf8'),
            headers={
                "content-type": "application/json",
            })
        body = json.loads(resp.content)

        # parse data
        question = get(body, 'data.question')

        Problem.replace(
            id=question['questionId'], display_id=question['questionFrontendId'], title=question["questionTitle"],
            level=question["difficulty"], slug=slug, description=question['content'],
            accepted=accepted
        ).execute()

        for item in question['topicTags']:
            if Tag.get_or_none(Tag.slug == item['slug']) is None:
                Tag.replace(
                    name=item['name'],
                    slug=item['slug']
                ).execute()

            ProblemTag.replace(
                problem=question['questionId'],
                tag=item['slug']
            ).execute()
        random_wait(1, 3)  # Small delay to avoid rate limiting

    def fetch_solution(self, slug):
        print(f"[*] Fetching solution for problem: {slug}")
        query_params = {
            "operationName": "QuestionNote",
            "variables": {"titleSlug": slug},
            "query": '''
            query QuestionNote($titleSlug: String!) {
                question(titleSlug: $titleSlug) {
                    questionId
                    article
                    solution {
                      id
                      content
                      contentTypeId
                      canSeeDetail
                      paidOnly
                      rating {
                        id
                        count
                        average
                        userRating {
                          score
                          __typename
                        }
                        __typename
                      }
                      __typename
                    }
                    __typename
                }
            }
            '''
        }
        resp = self.session.post("https://leetcode.com/graphql",
                                 data=json.dumps(query_params).encode('utf8'),
                                 headers={
                                     "content-type": "application/json",
                                 })
        body = json.loads(resp.content)

        # parse data
        solution = get(body, "data.question")
        solutionExist = solution['solution'] is not None and solution['solution']['paidOnly'] is False
        if solutionExist:
            Solution.replace(
                problem=solution['questionId'],
                url=f"https://leetcode.com/articles/{slug}/",
                content=solution['solution']['content']
            ).execute()
        random_wait(1, 3)  # Small delay to avoid rate limiting

    def fetch_submission(self, slug):
        print(f"[*] Fetching submission for problem: {slug}")
        query_params = {
            'operationName': "Submissions",
            'variables': {"offset": 0, "limit": 20, "lastKey": '', "questionSlug": slug},
            'query': '''query Submissions($offset: Int!, $limit: Int!, $lastKey: String, $questionSlug: String!) {
                                        submissionList(offset: $offset, limit: $limit, lastKey: $lastKey, questionSlug: $questionSlug) {
                                        lastKey
                                        hasNext
                                        submissions {
                                            id
                                            statusDisplay
                                            lang
                                            runtime
                                            timestamp
                                            url
                                            isPending
                                            __typename
                                        }
                                        __typename
                                    }
                                }'''
        }
        try:
            resp = self.session.post("https://leetcode.com/graphql",
                                     data=json.dumps(query_params).encode('utf8'),
                                     headers={
                                         "content-type": "application/json",
                                     })
            body = json.loads(resp.content)

            # parse data
            submissions = get(body, "data.submissionList.submissions")
            
            # filter for accepted submissions and find the latest one
            accepted_submissions = [sub for sub in submissions if sub['statusDisplay'] == 'Accepted']
            
            print(f"    - Total submissions returned: {len(submissions)}, Accepted: {len(accepted_submissions)}")
            
            if len(accepted_submissions) > 0:
                # sort by timestamp descending to get the latest submission first
                latest_submission = max(accepted_submissions, key=lambda x: x['timestamp'])
                
                print(f"    - Latest submission ID: {latest_submission['id']}, Timestamp: {latest_submission['timestamp']}")
                
                # check if this submission is already in the database
                existing = Submission.get_or_none(Submission.id == latest_submission['id'])
                if existing is None:
                    print(f"    - Submission not in DB, fetching code...")
                    try:
                        submission_id = latest_submission['id']
                        print(f"    - Fetching submission via GraphQL API...")
                        
                        # Use GraphQL API to fetch submission details
                        query_params = {
                            'operationName': "submissionDetails",
                            'variables': {"submissionId": submission_id},
                            'query': '''query submissionDetails($submissionId: Int!) {
                                submissionDetails(submissionId: $submissionId) {
                                    runtime
                                    runtimeDisplay
                                    runtimePercentile
                                    runtimeDistribution
                                    memory
                                    memoryDisplay
                                    memoryPercentile
                                    memoryDistribution
                                    code
                                    timestamp
                                    statusCode
                                    lang {
                                        name
                                        verboseName
                                    }
                                }
                            }'''
                        }
                        
                        submission_resp = self.session.post(
                            "https://leetcode.com/graphql",
                            data=json.dumps(query_params).encode('utf8'),
                            headers={"content-type": "application/json"}
                        )
                        
                        if submission_resp.status_code == 200:
                            submission_data = json.loads(submission_resp.content)
                            code = get(submission_data, "data.submissionDetails.code")
                            
                            if code:
                                Submission.insert(
                                    id=latest_submission['id'],
                                    slug=slug,
                                    language=latest_submission['lang'],
                                    created=latest_submission['timestamp'],
                                    source=code.encode('utf-8')
                                ).execute()
                                print(f"    - Submission saved successfully")
                            else:
                                print(f"    - WARNING: Cannot extract submission code for problem: {slug}")
                                print(f"    - Response data: {submission_data}")
                                # Don't fail, just skip this submission
                        else:
                            print(f"    - ERROR: Failed to fetch submission details, status: {submission_resp.status_code}")
                            print(f"    - Response: {submission_resp.text[:200]}")
                    
                    except Exception as e:
                        print(f"    - ERROR fetching submission code: {type(e).__name__}: {str(e)}")
                        print(f"    - Skipping this submission due to error")
                        # Don't crash, just skip and continue
                else:
                    print(f"    - Submission already in DB, skipping")
            else:
                print(f"    - No accepted submissions found")
        
        except Exception as e:
            print(f"    - ERROR in fetch_submission: {type(e).__name__}: {str(e)}")
            print(f"    - Continuing with next problem...")
        
        random_wait(1, 2)  # Small delay to avoid rate limiting


if __name__ == '__main__':
    create_tables()
    crawler = LeetCodeCrawler()
    crawler.login()
    crawler.fetch_accepted_problems()
