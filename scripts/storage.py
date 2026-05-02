from pathlib import Path
from datetime import date, datetime
import os
import yaml
import frontmatter


class JobCRM:
    """Handles all file system operations for the job search CRM."""

    def __init__(self, root_dir: str = "Job-Search") -> None:
        self.root = Path(root_dir)
        self.masters: Path = self.root / "masters"
        self.companies: Path = self.root / "companies"
        self._ensure_dirs([self.masters, self.companies])
        self._seed_masters()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _ensure_dirs(self, paths: list[Path]) -> None:
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)

    def _seed_masters(self) -> None:
        """Create placeholder master files if they don't exist yet."""
        placeholders = {
            "master_resume.md": "# Master Resume\nAdd your full resume content here.",
            "resume_template.md": "# Resume Template\nAdd your resume template here.",
            "cold_outreach.md": "# Cold Outreach Template\nWrite your outreach template here.",
            "follow_up.md": "# Follow-Up Template\nWrite your follow-up template here.",
            # Seeded so the `tasks` command has something to work with immediately
            "thank_you.md": "# Thank You Template\nWrite your post-interview thank you template here.",
            "monthly_checkin.md": "# Monthly Check-in Template\nWrite your monthly check-in template here.",
        }
        for filename, content in placeholders.items():
            path = self.masters / filename
            if not path.exists():
                path.write_text(content)

    # ------------------------------------------------------------------ #
    # Read helpers                                                         #
    # ------------------------------------------------------------------ #

    def read_master(self, filename: str) -> str:
        path = self.masters / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Master file '{filename}' not found in {self.masters}. "
                "Create it before running this command."
            )
        return path.read_text()

    def company_exists(self, company_name: str) -> bool:
        # FIX: use _company_dir so "My Company" and "My_Company" resolve the same way
        return self._company_dir(company_name).exists()

    def person_exists(self, company_name: str, person_name: str) -> bool:
        return self._person_dir(company_name, person_name).exists()

    def resume_exists(self, company_name: str, job_title: str) -> bool:
        app_file = self._app_dir(company_name, job_title) / "tailored_resume.md"
        return app_file.exists()
    
    def resume_pdf_exists(self, company_name: str, job_title: str) -> bool:
        app_file = self._app_dir(company_name, job_title) / "tailored_resume.pdf"
        return app_file.exists()

    def job_description_exists(self, company_name: str, job_title: str) -> bool:
        app_file = self._app_dir(company_name, job_title) / "job_description.md"
        return app_file.exists()

    def read_person_context(self, company_name: str, person_name: str) -> str:
        context_file = self._person_dir(company_name, person_name) / "context.md"
        if context_file.exists():
            return context_file.read_text()
        return ""

    def list_email_templates(self) -> list[str]:
        # BUG FIX 4: also exclude resume_template.md — it's not an email template
        excluded = {"master_resume.md", "resume_template.md"}
        return [
            f.name
            for f in self.masters.iterdir()
            if f.suffix == ".md" and f.name not in excluded
        ]

    # ------------------------------------------------------------------ #
    # Path builders                                                        #
    # ------------------------------------------------------------------ #

    def _company_dir(self, company_name: str) -> Path:
        return self.companies / company_name.replace(" ", "_")

    def _app_dir(self, company_name: str, job_title: str) -> Path:
        return self._company_dir(company_name) / "applications" / job_title.replace(" ", "_")

    def _person_dir(self, company_name: str, person_name: str) -> Path:
        return self._company_dir(company_name) / "people" / person_name.replace(" ", "_")

    # ------------------------------------------------------------------ #
    # Path Gets                                                            #
    # ------------------------------------------------------------------ #

    def get_log_path(self, company_name: str, person_name: str) -> Path:
        return self._person_dir(company_name, person_name) / "interaction_log.md"

    def get_resume_path(self, company_name: str, job_title: str) -> Path:
        return self._app_dir(company_name, job_title) / "tailored_resume.pdf"

    def read_job_description(self, company_name: str, job_title: str) -> str:
        path = self._app_dir(company_name, job_title) / "job_description.md"
        if not path.exists():
            raise FileNotFoundError(
                f"{str(path)} not found."
            )
        return path.read_text()

    # ------------------------------------------------------------------ #
    # Write operations                                                     #
    # ------------------------------------------------------------------ #

    def save_company(self, company_name: str, company_info: str) -> Path:
        company_dir = self._company_dir(company_name)
        (company_dir / "applications").mkdir(parents=True, exist_ok=True)
        (company_dir / "people").mkdir(parents=True, exist_ok=True)
        info_file = company_dir / "company_info.md"
        info_file.write_text(company_info)
        return info_file

    def save_person(
        self,
        company_name: str,
        person_name: str,
        context: str,
    ) -> Path:
        person_dir = self._person_dir(company_name, person_name)
        person_dir.mkdir(parents=True, exist_ok=True)

        context_file = person_dir / "context.md"
        if not context_file.exists():
            context_file.write_text(f"# Notes on {person_name}\n{context}")

        return context_file

    def save_application(
        self,
        company_name: str,
        job_title: str,
        url: str,
        job_description: str,
        tailored_resume: str,
    ) -> Path:
        app_dir = self._app_dir(company_name, job_title)
        app_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        post = frontmatter.Post(
            f"**URL:** {url}\n\n**Description:**\n{job_description}",
            title=job_title,
            company=company_name,
            status="applied",
            applied_date=today,
            url=url,
        )
        with open(app_dir / "job_description.md", "wb") as f:
            frontmatter.dump(post, f)

        (app_dir / "tailored_resume.md").write_text(tailored_resume)
        return app_dir

    def update_application_status(self, company_name: str, job_title: str, new_status: str) -> None:
        """Update the status field in job_description.md frontmatter."""
        path = self._app_dir(company_name, job_title) / "job_description.md"
        if not path.exists():
            raise FileNotFoundError(f"No application found for {job_title} at {company_name}.")
        post = frontmatter.load(str(path))
        post["status"] = new_status.lower()
        with open(path, "wb") as f:
            frontmatter.dump(post, f)

    def get_all_applications(self) -> list[dict]:
        """
        Walk every application folder and return a list of dicts with:
          company, title, status, applied_date, url
        Falls back gracefully for old job_description.md files without frontmatter.
        """
        apps = []
        for jd_file in self.companies.glob("*/applications/*/job_description.md"):
            company_name = jd_file.parent.parent.parent.name.replace("_", " ")
            job_title    = jd_file.parent.name.replace("_", " ")
            try:
                post = frontmatter.load(str(jd_file))
                status       = post.get("status", "applied")
                applied_date = post.get("applied_date", "unknown")
                url          = post.get("url", "")
            except Exception:
                # Old-format file without frontmatter — parse what we can
                raw = jd_file.read_text()
                status = "applied"
                applied_date = "unknown"
                url = ""
                for line in raw.splitlines():
                    if line.startswith("**URL:**"):
                        url = line.replace("**URL:**", "").strip()
            apps.append({
                "company":      company_name,
                "title":        job_title,
                "status":       status,
                "applied_date": applied_date,
                "url":          url,
            })

        status_order = {"applied": 0, "interviewing": 1, "offer": 2, "rejected": 3, "withdrawn": 4}
        apps.sort(key=lambda a: (status_order.get(a["status"], 99), a["applied_date"]))
        return apps

    def save_email_draft(
        self,
        company_name: str,
        person_name: str,
        draft: str,
    ) -> Path:
        person_dir = self._person_dir(company_name, person_name)
        person_dir.mkdir(parents=True, exist_ok=True)

        context_file = person_dir / "context.md"
        if not context_file.exists():
            context_file.write_text(f"# Notes on {person_name}\nAdd context here.")

        draft_file = person_dir / "draft_email.md"
        draft_file.write_text(draft)
        return draft_file

    def update_interaction_log(self, company: str, person: str, interaction_type: str, content: str):
        """Updates metadata and appends the email content to the log file."""
        # BUG FIX 1: was self._get_log_path — method is named get_log_path (no underscore)
        log_path = self.get_log_path(company, person)
        today = date.today().isoformat()

        if log_path.exists():
            post = frontmatter.load(str(log_path))
        else:
            post = frontmatter.Post("")

        post['last_contact_date'] = today
        post['last_contact_type'] = interaction_type
        
        new_entry = f"\n\n## {today} - {interaction_type.replace('_', ' ').title()}\n\n{content}\n"
        post.content += new_entry

        with open(log_path, 'wb') as f:
            frontmatter.dump(post, f)

    def get_pending_tasks(self):
        """Scans all people folders and returns tasks based on timing logic."""
        tasks = []
        today = date.today()
        # BUG FIX 2: was self.base_path — the attribute is self.root
        people_dir = self.root / "companies"
        
        for log_file in people_dir.glob("**/people/*/interaction_log.md"):
            post = frontmatter.load(str(log_file))
            
            person_name = log_file.parent.name.replace("_", " ")
            # BUG FIX 3: log_file.parent is the person dir, .parent is "people",
            # .parent again is the company dir — not .parent.parent.parent
            company_name = log_file.parent.parent.parent.name.replace("_", " ")
            
            last_date_str = post.get('last_contact_date')
            last_type = post.get('last_contact_type')

            if not last_date_str:
                continue

            last_date = datetime.strptime(str(last_date_str), "%Y-%m-%d").date()
            days_since = (today - last_date).days

            task_type = None

            if last_type == "cold_outreach" and days_since >= 3:
                task_type = "follow_up"
            elif last_type == "interview" and days_since >= 0:
                task_type = "thank_you"
            elif days_since >= 30:
                task_type = "monthly_checkin"

            if task_type:
                tasks.append({
                    "person": person_name,
                    "company": company_name,
                    "type": task_type,
                    "days_ago": days_since
                })
        
        return tasks