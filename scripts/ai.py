import requests
from bs4 import BeautifulSoup
from google import genai


# ------------------------------------------------------------------ #
# Web scraping                                                         #
# ------------------------------------------------------------------ #

def get_url_content(url: str) -> str:
    """Fetches a webpage and returns clean, readable text."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


# ------------------------------------------------------------------ #
# AI calls                                                             #
# ------------------------------------------------------------------ #

class JobAI:
    """Handles all AI-powered content generation via Gemini."""

    def __init__(self, model_name: str = "gemini-2.0-flash") -> None:
        self.client = genai.Client()
        self.model_name = model_name

    def _generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return response.text if response.text is not None else ""

    def extract_job_description(self, url: str) -> str:
        """Scrapes a job posting URL and extracts the clean job description."""
        print(f"  Fetching job posting from {url}...")
        raw_text = get_url_content(url)
        prompt = f"""
        Extract the Job Title and full Job Description from the following raw webpage text.
        Ignore navigation menus, footers, ads, and unrelated content.
        Format the output clearly in Markdown.

        RAW TEXT:
        {raw_text[:8000]}
        """
        return self._generate(prompt)

    def extract_company_info(self, url: str) -> str:
        """Scrapes a company website and summarizes key information."""
        print(f"  Fetching company info from {url}...")
        raw_text = get_url_content(url)
        prompt = f"""
        Based on the text from this company's website, write a concise summary covering:
        1. What the company does and who they serve.
        2. Their mission or core values.
        3. Any notable tech stack, products, or recent news mentioned.
        Format in Markdown.

        RAW TEXT:
        {raw_text[:8000]}
        """
        return self._generate(prompt)

    def tailor_resume(
        self,
        master_resume: str,
        job_description: str,
        job_title: str,
        company_name: str,
    ) -> str:
        """Generates a tailored resume based on the master resume and job description."""
        prompt = f"""
        I am applying for the role of {job_title} at {company_name}.
        Using my master resume and the job description below, create a tailored resume in Markdown.
        Emphasize the most relevant skills, experiences, and projects.
        Do not invent experience — only rearrange and reframe what is already there.

        MASTER RESUME:
        {master_resume}

        JOB DESCRIPTION:
        {job_description}
        """
        return self._generate(prompt)

    def draft_email(
        self,
        template: str,
        person_name: str,
        company_name: str,
        context_notes: str,
    ) -> str:
        """Drafts a personalized outreach email using a master template."""
        context_section = f"Additional context about {person_name}:\n{context_notes}" if context_notes else ""
        prompt = f"""
        Write a personalized outreach email based on the template below.
        Fill in the details naturally — do not leave placeholder brackets.
        Keep it concise and professional. Output in Markdown format.

        TEMPLATE:
        {template}

        TARGET PERSON: {person_name}
        COMPANY: {company_name}
        {context_section}
        """
        return self._generate(prompt)