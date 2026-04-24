# Job Search CRM

A local, AI-powered job search manager. It keeps your applications, tailored resumes, and outreach emails organized in a clean folder structure — no subscriptions, no dashboards, just files you own.

Built with [Gemini 2.0 Flash](https://deepmind.google/technologies/gemini/) and [Click](https://click.palletsprojects.com/).

---

## What it does

- **Scrapes job postings** and extracts clean job descriptions from any URL
- **Tailors your resume** to each role using your master resume as a base
- **Summarizes company info** from their website so you always have context
- **Drafts outreach emails** personalized to a specific person using your own templates
- **Organizes everything** into a predictable local folder structure

---

## Folder structure

After running a few commands, your `Job-Search/` directory will look like this:

```
Job-Search/
├── masters/
│   ├── master_resume.md       # Your full resume — edit this first
│   ├── cold_outreach.md       # Email template for cold outreach
│   └── follow_up.md           # Email template for follow-ups
└── companies/
    └── Stripe/
        ├── company_info.md    # AI-generated summary of the company
        ├── applications/
        │   └── Backend_Engineer/
        │       ├── job_description.md   # Scraped & cleaned JD
        │       └── tailored_resume.md   # AI-tailored resume
        └── people/
            └── Jane_Smith/
                ├── context.md           # Your notes on this person
                └── draft_email.md       # AI-drafted outreach email
```

---

## Setup

**1. Install uv (if you haven't already)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone the repo and install dependencies**

```bash
git clone <your-repo-url>
cd <your-repo-folder>
uv venv
uv sync
```

**3. Add your Gemini API key**

```bash
cp .env.example .env
```

Then open `.env` and replace the placeholder with your key:

```
GEMINI_API_KEY=your_actual_key_here
```

You can get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).

**4. Fill in your master resume**

Open `Job-Search/masters/master_resume.md` (created automatically on first run) and paste in your full resume. This is the source of truth the AI tailors from.

---

## Usage

### See all commands

```bash
uv run scripts/main.py --help
```

---

### Add a company

Creates a company folder and generates an AI summary of what they do.

```bash
uv run scripts/main.py add-company <CompanyName> <url>
```

```bash
uv run scripts/main.py add-company Stripe https://stripe.com
```

> If you run `apply` or `email` for a company that doesn't exist yet, it will prompt you to create it on the spot.

---

### Add a job application

Scrapes the job posting, generates a tailored resume, and saves everything under the company folder.

```bash
uv run scripts/main.py apply <CompanyName> "<Job Title>" <url>
```

```bash
uv run scripts/main.py apply Stripe "Backend Engineer" https://stripe.com/jobs/listing/123
```

---

### Draft an outreach email

Picks a template from your `masters/` folder and generates a personalized email for a specific person.

```bash
uv run scripts/main.py email <CompanyName> "<Person Name>"
```

```bash
uv run scripts/main.py email Stripe "Jane Smith"
```

You'll be prompted to choose a template and optionally add context notes (e.g. a LinkedIn bio snippet or how you met). If you've emailed this person before, any existing notes in their `context.md` are used automatically.

---

## Adding email templates

Any `.md` file you add to `Job-Search/masters/` (other than `master_resume.md`) will show up as an available template when you run the `email` command. Write them however you like — the AI will use them as a style and structure guide.

Example `masters/cold_outreach.md`:

```markdown
# Cold Outreach Template

Hi [Name],

I came across your work at [Company] and was really impressed by [something specific].

I'm a [your role] with experience in [relevant skills] and I'd love to connect...
```

---

## Project structure

```
<repo_name>/
├── scripts/
│   ├── main.py           # CLI commands (Click)
│   ├── storage.py        # File system operations
│   ├── ai.py             # Gemini API calls and web scraping
├── pyproject.toml
├── README.md
├── uv.lock
├── .env.example
├── .python_version
└── .gitignore
```

The three files are intentionally separated by concern. If you want to change how files are saved, touch only `storage.py`. If you want to change how the AI generates content, touch only `ai.py`.

---

## Important notes

- **Your `.env` file is gitignored.** Never commit it. Your `Job-Search/` folder is also gitignored since it will contain personal career info.
- **Job posting scraping may not work on all sites.** Some job boards (Workday, Greenhouse) render content with JavaScript that a basic HTTP scraper can't see. If the extracted JD looks empty, try copying the job description text manually into the saved `job_description.md`.
- **The AI does not invent resume content.** It only reframes and reorders what's already in your master resume.
