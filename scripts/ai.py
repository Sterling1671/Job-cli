from google import genai
from job_scraper import get_url_content


# ------------------------------------------------------------------ #
# AI calls                                                             #
# ------------------------------------------------------------------ #

class JobAI:
    """Handles all AI-powered content generation via Gemini."""

    def __init__(self, model_name: str = "gemini-2.5-flash") -> None:
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
        Preserve language that would be useful for ATS optimization
        Ignore navigation menus, footers, ads, and unrelated content.
        Format the output clearly in Markdown. Do not provide conversational filler.

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
        Format in Markdown. Do not provide conversational filler.

        RAW TEXT:
        {raw_text[:8000]}
        """
        return self._generate(prompt)

    def tailor_resume(
        self,
        master_resume: str,
        resume_template: str,
        job_description: str,
        job_title: str,
        company_name: str,
    ) -> str:
        """Generates a tailored resume based on the master resume and job description."""
        prompt = f"""
        Act as a technical resume writer specializing in Silicon/Hardware Engineering.
        Inputs:
            Master Resume (Source Data)
            HTML Template (Formatting)
            Job Description & Title (Target)
        Task:
        Generate a tailored resume by mapping data from the Master Resume into the Template.
        Strict Rules:
            Selection Logic: Rank experiences by technical relevancy to the Job Description. Prioritize hardware design (SystemVerilog, FPGAs, Microcontrollers) for engineering roles.
            Preserve Formatting: Keep all HTML tags and CSS styles exactly as provided. Replace {{VARIABLES}} and duplicate the `` blocks for each entry.
            Bullet Point Engineering: >    * Use the Action-Context-Result framework.
                Use "Engineering Verbs" if the job title is engineering based(Synthesized, Integrated, Validated, Implemented).
                CRITICAL: Do not hallucinate metrics. If a result isn't in the Master, focus the "Result" on the technical success of the system (e.g., "...resulting in a functional 60Hz VGA timing controller" instead of "increased efficiency").
            Education: Select exactly 2-3 bullets from the Master Resume that most closely align with the technical keywords in the Job Description. Each bullet can be no longer than 95 characters.
            Relevant Coursework: Select exactly 2-4 courses from the Master Resume that most closely align with the technical keywords in the Job Description. Format as: Course Title: Brief 1-sentence technical focus. Each line can be a max of 95 characters
            Personal Projects: Select exactly 2-3 personal projects from the Master Resume that most closely align with the technical keywords in the Job Description. Each Personal project should have 2-3 bullet points. Each bullet point can be a max of 95 characters
            Expirience: Select exactly 3 jobs from the Master Resume that most closely align with the technical keywords in the Job Description. Each job should list 2-3 bullet points. Each line can have no more than 95 characters
            Volunteer Expirience: Select exactly one from the master resume that most closely aligns with the technical keywords in the Job description. The listing should have 2-3 bullet points. Each line can have no more than 95 characters
            Skills Categorization: Group skills into logical clusters (e.g., Languages, Tools, Hardware Protocols). Do not just list every skill from the Master; prioritize those requested in the Job Description.
            Mapping: Ensure {{SKILLS_BULLETS}} is replaced with a categorized, bulleted list.
            Do not bold, underline, italicize or add any html or css unless indicated by the resume template. It should stay as plain text
            In order to make the resume as close to one page as possible, include at least 26 bullet points throughout the resume. Include no more than 30.
            If a technical achievement is already detailed in the Projects section, do not repeat the specific technical details in the Education bullets; use Education bullets for GPA, Honors, or unique Lab roles only.
            ATS Optimization: Naturally integrate keywords from the Job Description into the bullet points.
        Output:
        Provide the final Markdown/HTML content ready for rendering. Do not provide conversational filler. 

        Master Resume:
        {master_resume}

        Resume Template:
        {resume_template}

        Job Description:
        {job_description}
        
        Job Title:
        {job_title}
        
        Company Name:
        {company_name}
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
        Keep it concise and professional. Output in Markdown format. Do not provide conversational filler.

        TEMPLATE:
        {template}

        TARGET PERSON: {person_name}
        COMPANY: {company_name}
        {context_section}
        """
        return self._generate(prompt)