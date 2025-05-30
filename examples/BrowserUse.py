#https://www.youtube.com/watch?v=s6vU1xG3U7s
#https://github.com/browser-use/browser-use
#https://github.com/browser-use/browser-use/blob/main/examples/models/gemini.py

#TODO: Fatemeh 
# fix WARNING  [browser] ⚠️ Failed to grant browser permissions ['clipboard-read', 'clipboard-write', 'notifications']: 
# TargetClosedError: BrowserContext.grant_permissions: Target page, context or browser has been closed

import asyncio
import os
import sys
import pandas as pd
import csv
import logging
import asyncio
from pydantic import BaseModel, SecretStr
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Controller
from browser_use.agent.views import AgentHistoryList
from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession

os.environ["ANONYMIZED_TELEMETRY"] = "false"

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Job(BaseModel):
    company_code: str
    title: str
    link: str
    description: str
    location: str | None = None
    date: str | None = None

class Jobs(BaseModel):
    jobs: List[Job]

#93: AIzaSyC18vDwBUqIwN9guAjBVkEQ4-FJQ6DXmE0
#Elham: AIzaSyC35vuSZdZHztG705CmupF2mY90dQRRL44
#Hosseini: AIzaSyD5dHXUp9MtFZZmgOfDF680Mv6PDC_xfyg
#931: AIzaSyADp1CHmOeOvIusDA8Uz0VmJ9gSn-DP7KU
#ahmad: AIzaSyCbkoWmrFnhxM3U_R7l-8W7NvSfuenZaaY
api_key = 'AIzaSyC18vDwBUqIwN9guAjBVkEQ4-FJQ6DXmE0'
if not api_key:
    raise ValueError('GOOGLE_API_KEY is not set')

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))

class CompanyCrawler:
    def __init__(self, companies_csv_path='companies.csv', jobs_csv_path='jobs.csv'):
        self.default(companies_csv_path,jobs_csv_path)
    
    def default(self, companies_csv_path='companies.csv', jobs_csv_path='jobs.csv'):
        self.companies_csv_path = companies_csv_path
        self.jobs_csv_path = jobs_csv_path
        self.all_jobs = []
        
        # Initialize browser session
        self.browser_session = BrowserSession(
            browser_profile= BrowserProfile(
                viewport_expansion=0,
                user_data_dir='~/.config/browseruse/profiles/default',
            )
        )
        self.API_error = False   

    def load_companies(self):
        """Load companies from CSV file"""
        try:
            df = pd.read_csv(self.companies_csv_path)
            
            # Ensure required columns exist
            required_columns = ['company_code', 'company_website', 'crawled']
            for col in required_columns:
                if col not in df.columns:
                    if col == 'crawled':
                        df[col] = False
                    else:
                        raise ValueError(f"Required column '{col}' not found in CSV")
            
            return df
        except FileNotFoundError:
            logger.error(f"Companies CSV file '{self.companies_csv_path}' not found")
            # Create sample CSV file
            sample_data = {
                'company_code': ['32143900', '52143948'],
                'company_website': ['https://www.agrifac.com', 'https://www.agricopotatoes.com'],
                'crawled': [False, False]
            }
            pd.DataFrame(sample_data).to_csv(self.companies_csv_path, index=False)
            logger.info(f"Created sample CSV file: {self.companies_csv_path}")
            return pd.DataFrame(sample_data)
        except Exception as e:
            logger.error(f"Error loading companies CSV: {e}")
            raise
    
    def save_companies(self, df):
        """Save updated companies DataFrame back to CSV"""
        try:
            df.to_csv(self.companies_csv_path, index=False)
            logger.info(f"Updated companies CSV: {self.companies_csv_path}")
        except Exception as e:
            logger.error(f"Error saving companies CSV: {e}")
    
    def save_positions(self):
        """Save all found positions to JSON"""
        if not self.all_jobs:
            logger.info("No positions found to save")
            return
        
        try:
            print('108')                        
            self.write_list_to_csv(self.all_jobs,self.jobs_csv_path)
            print('114')
            logger.info(f"Saved '{len(self.all_jobs)}' jobs to '{self.jobs_csv_path}'")
        except Exception as e:
            logger.error(f"Error saving jobs JSON: {e}")
    
    async def run_search_for_company(self, company_code, website):
        """Run career search for a single company"""
        logger.info(f"Starting search for {company_code} - {website}")
        
        try:
            task = f"""Go to {website}, search for career, job, vacancy, position, work with us or other synonym of job link in Dutch or English.            
            For each job posting found, build the output with this exact structure:
                job: {{
                    "company_code": "company_code",
                    "title": "exact job title",
                    "link": "complete URL to job posting based on the extracted link",
                    "description": "brief description or requirements",
                    "location": "job location",
                    "date": "posted date of job if has it"
                }}

            Look for Dutch terms like: vacatures, banen, carrière, werkgelegenheid, werkenbij
            Look for English terms like: careers, jobs, positions, vacancies, employment

            Make sure to include the company code '{company_code}' for each position found in company_code field.
            Return the data as a JSON list of objects, matching jobs as the Jobs Pydantic model."""
            
            # Use the Controller with an output_model
            controller = Controller(              
                output_model=Jobs # Specify your Pydantic model here
            )

            # The agent will use this controller
            agent = Agent(
                task=task,
                llm=llm,
                controller=controller,
                browser_session=self.browser_session,
            )

            history_list = await agent.run(max_steps=25)
            result = history_list.final_result()
            if result:
                parsed: Jobs = Jobs.model_validate_json(result)
                logger.warning(f"{len(parsed.jobs)} jobs are extracted for '{company_code}' ('{website}')")
                return parsed.jobs
            else:
                logger.warning(f"Unable to parse output for '{company_code}' ('{website}')")
                return []


        except Exception as e:
            self.API_error = True
            logger.error(f"Error searching '{company_code}' ('{website}'): {e}")
            return []

    def write_list_to_csv(self,data_list, filename="output.csv", header=None):
        """
        Writes a list of lists (or list of dictionaries) to a CSV file.

        Args:
            data_list (list): The data to write.
                            Can be a list of lists (for row-wise data)
                            or a list of dictionaries (for data with headers).
            filename (str): The name of the CSV file to create or overwrite.
            header (list, optional): A list of strings to use as the header row.
                                    If data_list is a list of dictionaries,
                                    and header is None, the keys of the first
                                    dictionary will be used as the header.
                                    If data_list is a list of lists, and header
                                    is provided, it will be written as the first row.
                                    Defaults to None.
        """
        try:
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                # Determine if we're writing rows or dictionaries
                if data_list and isinstance(data_list[0], dict):
                    # If data is a list of dictionaries, use DictWriter
                    fieldnames = header if header else list(data_list[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data_list)
                else:
                    # If data is a list of lists (or other iterables), use writer
                    writer = csv.writer(csvfile)
                    if header:
                        writer.writerow(header)
                    writer.writerows(data_list)
            print(f"Successfully wrote data to '{filename}'")
        except IOError as e:
            print(f"Error writing to file '{filename}': {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


    async def process_all_companies(self):
        """Process all companies in the CSV file"""
        logger.info("Starting to process all companies")
        
        # Load companies
        df_companies = self.load_companies()
        
        # Filter uncrawled companies
        uncrawled = df_companies[df_companies['crawled'] == False]
        
        if uncrawled.empty:
            logger.info("All companies have already been crawled")
            return
        
        logger.info(f"Found '{len(uncrawled)}/{len(df_companies)}' companies to crawl")
        
        # Process each uncrawled company
        for index, row in uncrawled.iterrows():
            company_code = row['company_code']
            website = row['company_website']
            
            try:
                # Search for positions
                jobs = await self.run_search_for_company(company_code, website)
                
                if(self.API_error):
                    return
                # Add jobs to our collection
                if(jobs != [] and len(jobs) > 0):
                    self.all_jobs.extend(jobs)
                
                # Mark company as crawled
                df_companies.loc[df_companies['company_code'] == company_code, 'crawled'] = True
                
                # Save progress after each company
                self.save_companies(df_companies)
                self.save_positions()
                
                logger.info(f"Completed crawling '{company_code}'")
                
                # Add a small delay between companies to be respectful
                await asyncio.sleep(2)

                # TODO: Fatemeh
                print(f'Checking company = {index}')
                if(index > 1):
                    break
                    
            except Exception as e:
                logger.error(f"Failed to process '{company_code}': {e}")
                continue
        
        logger.info(f"Completed processing '{index + 1}' companies. Total positions found: '{len(self.all_jobs)}'")

async def main():
    """Main function to run the crawler"""
    try:
        i = 1
        while(i < 1000):
            crawler = CompanyCrawler()
            crawler.default()
            await crawler.process_all_companies()
            if(crawler.API_error):
                logger.error(f"Failed beacuse of invalid API Key")        
                break
            i = i + 1
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == '__main__':
    asyncio.run(main())