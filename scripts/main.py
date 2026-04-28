import os
import click
from dotenv import load_dotenv

from storage import JobCRM
from ai import JobAI
from autofill import autofill_application

# ------------------------------------------------------------------ #
# Bootstrap                                                            #
# ------------------------------------------------------------------ #

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise EnvironmentError("GEMINI_API_KEY is not set. Add it to your .env file.")

crm = JobCRM()
ai = JobAI()


# ------------------------------------------------------------------ #
# Shared helpers                                                       #
# ------------------------------------------------------------------ #

def _ensure_company(company_name: str) -> None:
    """Creates a company entry if one doesn't already exist."""
    if crm.company_exists(company_name):
        return

    click.echo(f"  Company '{company_name}' not found. Let's create it.")
    url = click.prompt("  Company website URL")
    try:
        company_info = ai.extract_company_info(url)
        saved = crm.save_company(company_name, company_info)
        click.echo(f"  ✓ Company info saved to {saved}")
    except Exception as e:
        click.echo(f"  ✗ Could not fetch company info: {e}")
        click.echo("  Creating company folder with empty info instead.")
        crm.save_company(company_name, f"# {company_name}\n\nAdd company info here.")

def _ensure_resume(company_name: str, job_title: str, url: str) -> None:
    """Creates a resume entry if one doesn't already exist."""
    _ensure_company(company_name)

    if crm.resume_exists(company_name, job_title):
        return

    if not crm.job_description_exists(company_name, job_title):
        try:
            job_description = ai.extract_job_description(url)
            # click.echo(f"Job Description: {job_description}") # Uncomment for testing
        except Exception as e:
            click.echo(f"✗ Could not fetch job description: {e}", err=True)
            return
    else:
        try:
            job_description = crm.read_job_description(company_name, job_title)
        except FileNotFoundError as e:
            click.echo(f"✗ {e}", err=True)
            return   

    try:
        master_resume = crm.read_master("master_resume.md")
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)
        return

    try:
        resume_template = crm.read_master("resume_template.md")
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)
        return

    click.echo("  Generating tailored resume...")
    tailored_resume = ai.tailor_resume(
        master_resume=master_resume,
        resume_template=resume_template,
        job_description=job_description,
        job_title=job_title,
        company_name=company_name,
    )

    app_dir = crm.save_application(
        company_name=company_name,
        job_title=job_title,
        url=url,
        job_description=job_description,
        tailored_resume=tailored_resume,
    )
    click.echo(f"✓ Application saved to {app_dir}")
    click.confirm("Please save the .md file to a pdf. Press enter when done",default=True)
    # Check for PDF before proceeding to browser automation
    while not crm.resume_pdf_exists(company_name, job_title):
        click.confirm(
            f"\n[!] Missing PDF: Please export the tailored resume for {job_title} to PDF.\n"
            f"Press Enter once the PDF is ready...", 
            default=True
        )
# ------------------------------------------------------------------ #
# Commands                                                             #
# ------------------------------------------------------------------ #

@click.group()
def cli() -> None:
    """Job Search CRM — manage applications, resumes, and outreach."""
    pass


@cli.command("add-company")
@click.argument("company_name")
@click.argument("url")
def add_company(company_name: str, url: str) -> None:
    """Create a company listing from their website URL.

    Example: python main.py add-company Stripe https://stripe.com
    """
    if crm.company_exists(company_name):
        click.echo(f"Company '{company_name}' already exists. Skipping.")
        return

    click.echo(f"Fetching info for {company_name}...")
    try:
        company_info = ai.extract_company_info(url)
        saved = crm.save_company(company_name, company_info)
        click.echo(f"✓ Saved company info to {saved}")
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)


@cli.command("create-resume")
@click.argument("company_name")
@click.argument("job_title")
@click.argument("url")
def create_resume(company_name: str, job_title: str, url: str) -> None:
    """Add a resume for a job application.

    Creates the company entry first if it doesn't exist yet.

    Example: python main.py create-resume Stripe "Backend Engineer" https://stripe.com/jobs/123
    """

    click.echo(f"Processing application for {job_title} at {company_name}...")
    
    if crm.resume_exists(company_name, job_title):
        click.echo("Resume already exists. Skipping.")
        return
    
    _ensure_resume(company_name, job_title, url)


@cli.command("apply")
@click.argument("company_name")
@click.argument("job_title")
@click.argument("url")
def apply(company_name: str, job_title: str, url: str) -> None:
    """Add an application for a job application.

    Creates the company entry and resume first if they don't exist yet.

    Example: python main.py apply Stripe "Backend Engineer" https://stripe.com/jobs/123
    """

    click.echo(f"Processing application for {job_title} at {company_name}...")

    _ensure_resume(company_name, job_title, url)

    click.echo(f"Opening application at {url}...")
    resume_path = str(crm.get_resume_path(company_name, job_title))
    profile = crm.read_master("profiles.json")

    autofill_application(url, profile, resume_path)

@cli.command("email")
@click.argument("company_name")
@click.argument("person_name")
def email(company_name: str, person_name: str) -> None:
    """Draft an outreach email to a person at a company.

    Creates the company and person entries if they don't exist yet.

    Example: python main.py email Stripe "Jane Smith"
    """
    _ensure_company(company_name)

    # Show available templates
    templates = crm.list_email_templates()
    if not templates:
        click.echo("✗ No email templates found in Job-Search/masters/. Add a .md template file first.", err=True)
        return

    click.echo("Available email templates:")
    for i, name in enumerate(templates, start=1):
        click.echo(f"  {i}. {name}")

    template_choice = click.prompt("Choose a template by number", type=int)
    if not 1 <= template_choice <= len(templates):
        click.echo("✗ Invalid choice.", err=True)
        return

    template_filename = templates[template_choice - 1]

    try:
        template = crm.read_master(template_filename)
    except FileNotFoundError as e:
        click.echo(f"✗ {e}", err=True)
        return

    # Read existing context if person already exists
    context_notes = crm.read_person_context(company_name, person_name)
    if context_notes:
        click.echo(f"  Found existing context notes for {person_name}.")
    else:
        click.echo(f"  No existing context for {person_name}.")
        context_notes = click.prompt(
            "  Add any context notes (LinkedIn bio snippet, how you met, etc.) or press Enter to skip",
            default="",
        )

    click.echo(f"  Drafting email to {person_name}...")
    draft = ai.draft_email(
        template=template,
        person_name=person_name,
        company_name=company_name,
        context_notes=context_notes,
    )

    saved = crm.save_email_draft(company_name, person_name, draft)
    click.echo(f"✓ Email draft saved to {saved}")

@cli.command("tasks")
def show_tasks():
    """Scan all contacts and identify pending outreach tasks."""
    pending = crm.get_pending_tasks() # You'll implement this in storage.py
    
    if not pending:
        click.echo("☀️ No pending tasks! You're all caught up.")
        return

    for task in pending:
        click.echo(f"[{task['type'].upper()}] {task['person']} @ {task['company']}")
        if click.confirm(f"Draft {task['type']} for {task['person']}?"):
            # 1. Generate the draft using AI
            draft = ai.draft_email(
                template=crm.read_master(f"{task['type']}.md"),
                person_name=task['person'],
                company_name=task['company'],
                context_notes=crm.read_person_context(task['company'], task['person'])
            )
            
            # 2. Let the user edit the draft manually
            edited_draft = click.edit(draft)
            
            if edited_draft and click.confirm("Mark as sent and update logs?"):
                crm.update_interaction_log(
                    task['company'], 
                    task['person'], 
                    task['type'], 
                    edited_draft
                )
                click.echo("✓ Log updated.")
# ------------------------------------------------------------------ #
# Entrypoint                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    cli()
