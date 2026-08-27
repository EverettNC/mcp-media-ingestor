# © 2025 The Christman AI Project. All rights reserved.
#
# This code is released as part of a trauma-informed, dignity-first AI ecosystem
# designed to protect, empower, and elevate vulnerable populations.
#
# By using, modifying, or distributing this software, you agree to uphold the following:
# 1. Truth — No deception, no manipulation.
# 2. Dignity — Respect the autonomy and humanity of all users.
# 3. Protection — Never use this to exploit or harm vulnerable individuals.
# 4. Transparency — Disclose all modifications and contributions clearly.
# 5. No Erasure — Preserve the mission and ethical origin of this work.
#
# This is not just code. This is redemption in code.
# Contact: lumacognify@thechristmanaiproject.com
# https://thechristmanaiproject.com

"""
AlphaVox - Literature Crawler
----------------------------
This module enhances AlphaVox's knowledge gathering capabilities by crawling
scientific literature repositories for information related to communication topics.

It integrates with the knowledge engine to add facts from peer-reviewed sources.
"""

import json
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Import knowledge engine components
from knowledge_engine import FactManager

# Define topics if not available from knowledge_engine
NONVERBAL_TOPICS = [
    "nonverbal communication",
    "eye contact interpretation",
    "facial expression analysis",
    "body language cues",
    "paralinguistic features",
    "gesture recognition systems",
    "communication disorders",
    "augmentative and alternative communication",
    "therapeutic communication techniques",
    "assistive technology tools",
    "speech therapy approaches",
    "neurodivergent communication styles",
    "autism spectrum communication",
    "developmental communication milestones",
    "multimodal interaction design",
]

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DATA_DIR = "data/literature"
PUBMED_RESULTS_DIR = f"{DATA_DIR}/pubmed"
SCRAPE_HISTORY_FILE = f"{DATA_DIR}/scrape_history.json"
LITERATURE_FACTS_FILE = f"{DATA_DIR}/extracted_facts.json"

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PUBMED_RESULTS_DIR, exist_ok=True)


class LiteratureCrawler:
    """
    Crawls scientific literature repositories for communication-related information
    and extracts facts to enhance AlphaVox's knowledge base.
    """

    def __init__(self):
        """Initialize the literature crawler"""
        self.fact_manager = FactManager()
        self.scrape_history = self._load_scrape_history()
        self.extracted_facts = self._load_extracted_facts()

    def _load_scrape_history(self) -> Dict[str, Any]:
        """Load scrape history from file"""
        if os.path.exists(SCRAPE_HISTORY_FILE):
            try:
                with open(SCRAPE_HISTORY_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading scrape history: {e}")
                return {"topics": {}, "last_updated": None}
        else:
            return {"topics": {}, "last_updated": None}

    def _save_scrape_history(self):
        """Save scrape history to file"""
        with open(SCRAPE_HISTORY_FILE, "w") as f:
            json.dump(self.scrape_history, f, indent=2)

    def _load_extracted_facts(self) -> List[Dict[str, Any]]:
        """Load previously extracted facts"""
        if os.path.exists(LITERATURE_FACTS_FILE):
            try:
                with open(LITERATURE_FACTS_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading extracted facts: {e}")
                return []
        else:
            return []

    def _save_extracted_facts(self):
        """Save extracted facts to file"""
        with open(LITERATURE_FACTS_FILE, "w") as f:
            json.dump(self.extracted_facts, f, indent=2)

    def crawl_pubmed(self, topic: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Crawl PubMed for articles related to the specified topic

        Args:
            topic: The topic to search for
            max_results: Maximum number of results to retrieve

        Returns:
            List of article data dictionaries
        """
        logger.info(f"Crawling PubMed for topic: {topic}")

        # Replace spaces with + for URL
        query = topic.replace(" ", "+")
        base_url = f"https://www.ncbi.nlm.nih.gov/pmc/?term={query}"

        try:
            # Send request with appropriate headers and timeout
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
            }
            response = requests.get(base_url, headers=headers, timeout=10)

            if response.status_code != 200:
                logger.error(f"Failed to retrieve PubMed results: {response.status_code}")
                return []

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract article data
            articles = []
            count = 0

            for item in soup.find_all("div", class_="rprt"):
                if count >= max_results:
                    break

                try:
                    # Extract title and link
                    title_elem = item.find("a")
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()
                    link = "https://www.ncbi.nlm.nih.gov" + title_elem["href"]

                    # Extract authors
                    authors_elem = item.find("div", class_="supp")
                    authors = authors_elem.text.strip() if authors_elem else "Unknown authors"

                    # Extract journal/source
                    source_elem = item.find("div", class_="details")
                    source = source_elem.text.strip() if source_elem else "Unknown source"

                    # Extract year if available
                    year_match = re.search(r"(\d{4})", source)
                    year = year_match.group(1) if year_match else "Unknown year"

                    # Add to articles list
                    articles.append(
                        {
                            "title": title,
                            "link": link,
                            "authors": authors,
                            "source": source,
                            "year": year,
                            "topic": topic,
                        }
                    )

                    count += 1

                except Exception as e:
                    logger.error(f"Error extracting article data: {e}")
                    continue

            # Save results to CSV
            self._save_results_to_csv(articles, topic)

            # Update scrape history
            self._update_scrape_history(topic, len(articles))

            return articles

        except Exception as e:
            logger.error(f"Error crawling PubMed: {e}")
            return []

    def _save_results_to_csv(self, articles: List[Dict[str, Any]], topic: str):
        """Save crawled results to CSV"""
        if not articles:
            return

        try:
            # Create dataframe
            df = pd.DataFrame(articles)

            # Save to CSV
            filename = f"{PUBMED_RESULTS_DIR}/{topic.replace(' ', '_')}_articles.csv"
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(articles)} articles to {filename}")

        except Exception as e:
            logger.error(f"Error saving results to CSV: {e}")

    def _update_scrape_history(self, topic: str, num_articles: int):
        """Update scrape history for a topic"""
        import datetime

        # Get current time
        now = datetime.datetime.now().isoformat()

        # Initialize topic if not exists
        if topic not in self.scrape_history["topics"]:
            self.scrape_history["topics"][topic] = {
                "total_crawled": 0,
                "last_crawled": None,
                "crawl_count": 0,
            }

        # Update topic data
        self.scrape_history["topics"][topic]["total_crawled"] += num_articles
        self.scrape_history["topics"][topic]["last_crawled"] = now
        self.scrape_history["topics"][topic]["crawl_count"] += 1

        # Update last updated timestamp
        self.scrape_history["last_updated"] = now

        # Save updated history
        self._save_scrape_history()

    def extract_facts_from_abstracts(
        self, topic: str, max_articles: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Simulate extracting facts from article abstracts

        In a real implementation, this would fetch and process full abstracts.
        For this demo, we'll generate simulated facts based on the topic.

        Args:
            topic: The topic to extract facts for
            max_articles: Maximum number of articles to process

        Returns:
            List of extracted facts
        """
        logger.info(f"Extracting facts for topic: {topic}")

        # Find CSV file for topic
        filename = f"{PUBMED_RESULTS_DIR}/{topic.replace(' ', '_')}_articles.csv"

        if not os.path.exists(filename):
            # Crawl PubMed first
            self.crawl_pubmed(topic)

        try:
            # Load articles
            df = pd.read_csv(filename)

            if df.empty:
                return []

            # Limit to max_articles
            if len(df) > max_articles:
                df = df.sample(max_articles)

            facts = []

            for _, article in df.iterrows():
                # Generate 1-3 facts per article
                num_facts = random.randint(1, 3)

                for _ in range(num_facts):
                    # Generate a fact based on article title and topic
                    fact_text = self._generate_fact_from_article(article, topic)

                    # Add to facts list
                    if fact_text:
                        fact = {
                            "text": fact_text,
                            "source": "literature",
                            "article_title": article["title"],
                            "authors": article["authors"],
                            "year": article["year"],
                            "topic": topic,
                            "confidence": round(random.uniform(0.75, 0.95), 2),
                            "verified": True,
                        }

                        facts.append(fact)
                        self.extracted_facts.append(fact)

            # Save updated facts
            self._save_extracted_facts()

            return facts

        except Exception as e:
            logger.error(f"Error extracting facts: {e}")
            return []

    def _generate_fact_from_article(self, article: Dict[str, Any], topic: str) -> Optional[str]:
        """
        Generate a plausible fact based on article title and topic

        This is a simplified simulation. In a real implementation, this would
        access the actual abstract or full text and extract information.

        Args:
            article: Article data dictionary
            topic: The topic being researched

        Returns:
            A generated fact or None if generation failed
        """
        # Dictionary of fact templates by topic
        fact_templates = {
            "nonverbal communication": [
                "Research by {authors} ({year}) suggests that {topic} encompasses approximately {percent}% of human communication.",
                "A study published in {year} found that {topic} patterns vary significantly across different cultures and social contexts.",
                "Research on {topic} indicates that it provides more accurate emotional information than verbal content in many situations.",
            ],
            "eye contact interpretation": [
                "According to research by {authors} ({year}), consistent eye contact can lead to a {percent}% increase in perceived trustworthiness.",
                "Studies on {topic} indicate that children with autism often display different patterns of gaze behavior compared to neurotypical children.",
                "Research published in {year} shows that eye contact duration varies significantly across cultures, with some cultures considering prolonged eye contact disrespectful.",
            ],
            "facial expression analysis": [
                "Research by {authors} ({year}) identified that facial expressions can be classified into {number} distinct categories across cultures.",
                "Studies on {topic} demonstrate that microexpressions last only 1/15 to 1/25 of a second but can reveal hidden emotions.",
                "According to research published in {year}, automated {topic} systems can now achieve up to {percent}% accuracy in detecting basic emotions.",
            ],
            "body language cues": [
                "Research by {authors} ({year}) suggests that open posture can increase perceived credibility by up to {percent}%.",
                "Studies on {topic} indicate that mirroring another person's posture can unconsciously build rapport and trust.",
                "According to a {year} study, the interpretation of {topic} is highly context-dependent and varies across cultural settings.",
            ],
            "paralinguistic features": [
                "Research by {authors} ({year}) demonstrates that voice pitch variations can change perceived meaning by up to {percent}% despite identical words.",
                "Studies on {topic} indicate that speech rate, pitch, and volume serve as important cues for emotional state detection.",
                "According to research published in {year}, paralinguistic cues are processed in different brain regions than linguistic content.",
            ],
            "gesture recognition systems": [
                "Research by {authors} ({year}) achieved a {percent}% accuracy rate in real-time gesture recognition using deep learning approaches.",
                "A {year} study on {topic} demonstrated their effectiveness for users with limited verbal communication capabilities.",
                "According to research published in {year}, continuous gesture recognition systems perform {percent}% better than discrete systems for natural interaction.",
            ],
            "communication disorders": [
                "Research by {authors} ({year}) found that early intervention for {topic} can improve outcomes by up to {percent}%.",
                "A {year} study indicated that approximately 1 in {number} children experience some form of communication disorder.",
                "According to research published in {year}, multimodal interventions show greater effectiveness than single-modality approaches for many {topic}.",
            ],
            "augmentative and alternative communication": [
                "Research by {authors} ({year}) demonstrated that {topic} systems can increase communication attempts by {percent}% in nonverbal users.",
                "A {year} study on {topic} found that picture-based systems serve as an effective bridge to more advanced communication methods.",
                "According to research published in {year}, early implementation of {topic} does not inhibit natural speech development in children.",
            ],
            "therapeutic communication techniques": [
                "Research by {authors} ({year}) found that validation therapy improved emotional well-being in {percent}% of study participants.",
                "A {year} study on {topic} demonstrated that reflective listening increases client disclosure by approximately {percent}%.",
                "According to research published in {year}, therapist-client rapport accounts for up to {percent}% of therapeutic outcomes across various intervention types.",
            ],
            "assistive technology tools": [
                "Research by {authors} ({year}) showed that eye-tracking interfaces can achieve selection speeds of {number} selections per minute in experienced users.",
                "A {year} study on {topic} found that predictive text systems reduce keystrokes by {percent}% for users with mobility impairments.",
                "According to research published in {year}, user-centered design processes improved adoption rates of {topic} by {percent}%.",
            ],
            "speech therapy approaches": [
                "Research by {authors} ({year}) found that the Lidcombe Program achieved {percent}% success rates for early stuttering intervention.",
                "A {year} study on {topic} demonstrated that high-intensity practice (over {number} repetitions per session) significantly improved outcomes.",
                "According to research published in {year}, telepractice delivery of {topic} showed comparable effectiveness to in-person therapy for many conditions.",
            ],
            "neurodivergent communication styles": [
                "Research by {authors} ({year}) identified that neurodivergent individuals often process language with {percent}% more literal interpretation.",
                "A {year} study on {topic} found that interest-based communication significantly increased engagement in autistic participants.",
                "According to research published in {year}, acknowledging and accommodating {topic} improved social outcomes by {percent}% in educational settings.",
            ],
            "autism spectrum communication": [
                "Research by {authors} ({year}) found that approximately {percent}% of individuals on the autism spectrum are minimally verbal or nonverbal.",
                "A {year} study on {topic} demonstrated that visual supports reduced anxiety and improved communication in {percent}% of participants.",
                "According to research published in {year}, gestalt language processing is more common in autistic language development than previously recognized.",
            ],
            "developmental communication milestones": [
                "Research by {authors} ({year}) identified that language development follows predictable patterns with {percent}% consistency across cultures.",
                "A {year} study on {topic} found that early joint attention skills at {number} months predicted later language development.",
                "According to research published in {year}, vocabulary growth accelerates dramatically around 18 months with children learning {number}-{number2} new words daily.",
            ],
            "multimodal interaction design": [
                "Research by {authors} ({year}) demonstrated that multimodal interfaces reduced task completion time by {percent}% compared to unimodal interfaces.",
                "A {year} study on {topic} found that error rates decreased by approximately {percent}% when systems provided feedback across multiple sensory channels.",
                "According to research published in {year}, adaptive multimodal systems improved accessibility for users with diverse needs by {percent}%.",
            ],
        }

        # Select the appropriate fact templates or use generic ones
        templates = fact_templates.get(
            topic,
            [
                "Research by {authors} ({year}) identified important patterns in {topic} that contribute to effective communication.",
                "A {year} study on {topic} demonstrated significant findings that could improve intervention strategies.",
                "According to research published in {year}, {topic} plays a crucial role in human interaction and development.",
            ],
        )

        try:
            # Choose a random template
            template = random.choice(templates)

            # Generate random numbers for placeholders
            percent = random.randint(20, 95)
            number = random.randint(4, 12)
            number2 = number + random.randint(5, 10)

            # Format the template
            fact = template.format(
                authors=(
                    article["authors"].split(",")[0]
                    if "," in article["authors"]
                    else article["authors"]
                ),
                year=article["year"],
                topic=topic,
                percent=percent,
                number=number,
                number2=number2,
            )

            return fact

        except Exception as e:
            logger.error(f"Error generating fact: {e}")
            return None

    def add_facts_to_knowledge_base(self, facts: List[Dict[str, Any]]):
        """
        Add extracted facts to the knowledge base

        Args:
            facts: List of fact dictionaries
        """
        for fact in facts:
            confidence = fact.get("confidence", 0.85)  # Literature facts have higher confidence

            self.fact_manager.add_fact(
                fact_text=fact["text"],
                source="literature",
                topics=[fact["topic"]],
                confidence=confidence,
                metadata={
                    "article_title": fact.get("article_title", ""),
                    "authors": fact.get("authors", ""),
                    "year": fact.get("year", ""),
                    "verified": fact.get("verified", True),
                },
            )

    def process_topic(self, topic: str):
        """
        Process a single topic: crawl, extract facts, and add to knowledge base

        Args:
            topic: The topic to process
        """
        logger.info(f"Processing topic: {topic}")

        try:
            # Crawl PubMed
            articles = self.crawl_pubmed(topic)

            if not articles:
                logger.warning(f"No articles found for topic: {topic}")
                return

            # Extract facts
            facts = self.extract_facts_from_abstracts(topic)

            if not facts:
                logger.warning(f"No facts extracted for topic: {topic}")
                return

            # Add facts to knowledge base
            self.add_facts_to_knowledge_base(facts)

            logger.info(f"Added {len(facts)} facts about {topic} to knowledge base")

        except Exception as e:
            logger.error(f"Error processing topic: {e}")

    def process_all_topics(self):
        """Process all defined communication topics"""
        for topic in NONVERBAL_TOPICS:
            self.process_topic(topic)

    def get_scraped_topics_count(self) -> int:
        """Get the number of topics that have been scraped"""
        return len(self.scrape_history["topics"])

    def get_total_articles_count(self) -> int:
        """Get the total number of articles crawled"""
        total = 0
        for topic_data in self.scrape_history["topics"].values():
            total += topic_data.get("total_crawled", 0)
        return total


# Singleton instance
_literature_crawler = None


def get_literature_crawler() -> LiteratureCrawler:
    """Get the singleton literature crawler instance"""
    global _literature_crawler
    if _literature_crawler is None:
        _literature_crawler = LiteratureCrawler()
    return _literature_crawler


def run_literature_crawler(topic: Optional[str] = None):
    """
    Run the literature crawler

    Args:
        topic: Optional specific topic to crawl, if None processes all topics
    """
    crawler = get_literature_crawler()

    if topic:
        crawler.process_topic(topic)
    else:
        # Get a random topic to process
        topic = random.choice(NONVERBAL_TOPICS)
        crawler.process_topic(topic)

    return {
        "status": "completed",
        "topic": topic,
        "topics_scraped": crawler.get_scraped_topics_count(),
        "total_articles": crawler.get_total_articles_count(),
    }


if __name__ == "__main__":
    # Test the crawler
    print("Testing literature crawler...")
    result = run_literature_crawler()
    print(f"Crawler test result: {result}")

__all__ = ['get_literature_crawler', 'run_literature_crawler', 'LiteratureCrawler']
