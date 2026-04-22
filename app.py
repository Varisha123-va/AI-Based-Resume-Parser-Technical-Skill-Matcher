from flask import Flask, render_template, request, session, redirect, url_for
import pandas as pd
import os
import time
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import re

TECH_SKILLS = [
    "python","java","c","c++","javascript","html","css","react","nodejs",
    "django","flask","sql","mongodb","api","git","linux",
    "machine learning","deep learning","opencv","pandas","numpy",
    "autocad","revit","matlab","solidworks","ansys","catia",
    "arduino","raspberry pi","iot","embedded","microcontroller",
    "excel","tally","power bi","sap",
    "photoshop","illustrator","figma","ui","ux"
]

def extract_tech_skills(text):
    found = []
    text_clean = text.lower()
    for skill in TECH_SKILLS:
        # Strict match: sirf wahi words jo list mein hain
        if skill in text_clean:
            found.append(skill)
    return list(set(found))

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def index():

    if not session.get('logged_in'):
        return redirect(url_for('login'))

    referrer = request.referrer
    if not referrer or ('result' not in referrer and 'roadmap' not in referrer):
        session.clear()
        session['logged_in'] = True 

    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():

    # Jaise hi login page open ho, pichla sab delete kar do

    if request.method == 'GET':
        session.clear()

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if email and password:
            session['logged_in'] = True
            session['user_email'] = email
            
            return redirect(url_for('index'))

        return redirect(url_for('index', t=int(time.time())))

    return render_template('login.html')


@app.route('/new-run')
def new_run():
    session.clear()  
    return redirect('/')



@app.route('/upload-page')
def upload_page():
    return render_template('index.html')



@app.route('/processing')
def processing():
    return render_template('processing.html')


@app.route('/roadmap')
def roadmap():
    missing_skills = session.get('missing_skills', [])
    field = session.get('detected_field', 'General')
    return render_template('roadmap.html', skills=missing_skills, field=field)


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def matched_skills(resume, job):
    matches = []
    for word in job.split():
        if word in resume:
            matches.append(word)
    return list(set(matches))


@app.route('/analyze', methods=['POST'])
def analyze():

    # ✅ STEP 1: aliases
    skill_aliases = {
        "react": ["react", "reactjs", "react.js"],
        "javascript": ["js", "javascript"],
        "machine learning": ["ml", "machine learning"],
    }

    # ✅ STEP 2: function
    def skill_found(technical_skill, text):
        if technical_skill in skill_aliases:
            return any(alias in text for alias in skill_aliases[technical_skill])
        return technical_skill in text


    file = request.files.get('resume')

   # matched_skills = []

    file = request.files.get('resume')

    filepath = None

    extra_skills_input = request.form.get("extra_skills", "").lower()
    user_description = request.form.get("job_desc", "").lower()

# --- FILE HANDLING ---

    if file and file.filename != "":

        UPLOAD_FOLDER = "uploads"

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)

        file.save(filepath)

        session['file_path'] = filepath

        session['file_name'] = file.filename

        session['resume_uploaded'] = True

    elif session.get('file_path'):
        filepath = session.get('file_path')
    if not filepath:
        return "<h1>❌ Error: Please upload a file first!</h1><a href='/'>Back</a>"

    job_desc = request.form.get("job_desc")

# --- TEXT EXTRACTION ---

    text = ""
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text

        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)

        resume_text_lower = text.lower()
          

    except Exception as e:
        return f"<h1>❌ Error reading PDF: {e}</h1><a href='/'>Back</a>"

# --- 1. ALL-FIELDS DICTIONARY (Missing Skills Logic) ---

    field_skills = {

        "Electronic Engineer": ["pcb design", "robotics design", "embedded systems", "iot", 
                                "internet of things", "circuit analysis", "matlab", "python", 
                                "microcontroller", "digital signal processing", "vlsi","communication systems", 
                                "electronics", "btech", "embedded c"],
        "Embedded Systems Engineer": ["embedded systems", "robotics", "iot", "microcontroller", 
                                      "sensors", "raspberry pi", "python", "circuit analysis", 
                                      "pcb design", "embedded c", "microcontroller concepts"],
        "Robotics Research Engineer": ["robotics design", "arduino", "sensors", "microcontrollers", 
                                       "embedded systems", "automation", "circuit debugging"],
        "IoT Specialist": ["iot", "internet of things", "sensors", "wireless communication", "embedded systems", 
                           "raspberry pi", "python"],
        "Frontend": ["html", "css", "javascript", "react", "angular", "vuejs", "typescript", "figma", "tailwind"],
        "Backend": ["nodejs", "express", "python", "django", "flask", "java", "sql", "mongodb", "api"],
        "Software Engineering": ["algorithms", "data structures", "git", "linux", "testing", "cloud", "c++", "c#"],
        "Electronic": ["pcb design", "microcontrollers", "embedded", "vlsi", "matlab", "arduino", "circuits"],
        "Architecture": ["autocad", "sketchup", "revit", "bim", "interior design", "3d modeling", "architecture"],
        "Fashion": ["textile", "fashion illustration", "pattern making", "garment", "sketching", "merchandising"],
        "Civil": ["autocad", "revit", "structural analysis", "surveying", "concrete", "hydraulics", "construction"],
        "Chemical": ["thermodynamics", "heat transfer", "mass transfer", "aspentech", "fluid mechanics", "kinetics"],
        "Medical": ["diagnosis", "pharmacology", "anatomy", "physiology", "pathology", "clinical", "surgery"],
        "Nursing": ["patient monitoring", "vital signs", "iv therapy", "bls", "acls", "healthcare", "nursing"],
        "Pharmacy": ["drug formulation", "toxicology", "pharmacology", "clinical trials", "medical coding"],
        "Graphic Design": ["photoshop", "illustrator", "figma", "branding", "typography", "video editing"],
        "Human Resources": ["recruitment", "payroll", "onboarding", "employee relations", "talent acquisition"],
        "Finance": ["accounting", "tally", "excel", "gst", "auditing", "taxation", "banking"],
        "Sales & Marketing": ["digital marketing", "seo", "crm", "lead generation", "market research", "branding"],
        "Legal": ["legal research", "litigation", "drafting", "contract law", "corporate law", "advocacy"],
        "Data Science":["data analysis", "eda", "predictive analytics", "python", "sql", "genai", "machine learning"]

       
}

    resume_text_lower = text.lower()
    detected_field = "General"
    missing_skills = []
    max_matches = 0

# Field Detection & Missing Skills Calculation

    for field, technical_skills in field_skills.items():
        matches = []

        for technical_skill in technical_skills:
            if skill_found(technical_skill, resume_text_lower):
               matches.append(technical_skill)

        if len(matches) >= 2 and len(matches) > max_matches:
           max_matches = len(matches)
           detected_field = "Skill-Based"

           missing_skills = [
               skill for skill in technical_skills 
               if not skill_found(skill, resume_text_lower)
               ][:8]

# --- 2. SMART JOB MATCHING (TF-IDF Ranking) ---

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "jobs.csv")

    if not os.path.exists(file_path):
        return "<h1>❌ Error: jobs.csv not found!</h1>"
    jobs = pd.read_csv(file_path)

# --- RESUME → TECH SKILLS ---
    tech_skills_resume = extract_tech_skills(resume_text_lower)

    if not tech_skills_resume:
       tech_skills_resume = resume_text_lower.split()[:20]  # fallback

    combined_user_profile = " ".join(tech_skills_resume)

    print("Resume Skills:", tech_skills_resume)

# --- JOBS → TECH SKILLS ---
    clean_jobs_desc = []

    for desc in jobs["description"]:
        desc = str(desc).lower()
        job_skills = extract_tech_skills(desc)
        clean_jobs_desc.append(" ".join(job_skills))

    documents = [combined_user_profile] + clean_jobs_desc

    print("Resume Text:", combined_user_profile[:200])
    print("Jobs:", clean_jobs_desc[:2])

    tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1,2))
    tfidf_matrix = tfidf.fit_transform(documents)

    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])

    print("Similarity Scores:", similarity[0][:5])


    def keyword_score(resume, job):
       count = 0
       for word in job.split():
         if word in resume:
            count += 1
       return count

    jobs["Keyword Score"] = jobs["description"].apply(
    lambda x: keyword_score(combined_user_profile, str(x).lower())
)

    jobs["Match Percentage"] = (similarity[0] * 100)

    jobs["Matched Skills"] = jobs["description"].apply(
    lambda x: matched_skills(combined_user_profile, str(x).lower())
)
    
    def strict_filter(row, resume_text):
      job_title = str(row['job_title']).lower()
    # Agar Job Title mein niche diye gaye words hain par resume mein nahi
      critical_terms = ["chemical", "hr", "nurse", "civil", "architecture", "legal"]
    
      for term in critical_terms:
        if term in job_title and term not in resume_text.lower():
            return 0  # Seedha score zero kar do
      return row["Match Percentage"]
    
    jobs["Match Percentage"] = jobs.apply(lambda r: strict_filter(r, resume_text_lower), axis=1)

# --- 3. DYNAMIC RESULTS ---

    results_df = jobs.sort_values(by="Match Percentage", ascending=False)

# remove low quality matches
    results_df = results_df[results_df["Match Percentage"] > 5]

    results_df = results_df.head(5)
    results_list = results_df.to_dict(orient="records")


    score = round(jobs["Match Percentage"].max(), 2) if not jobs.empty else 0

# Match Level

    if score > 80: level = "Excellent Match ✅"
    elif score > 60: level = "Good Match 👍"
    elif score > 40: level = "Average Match 🙂"
    else: level = "Low Match ⚠️"

# Perfect Matches (100%)
    perfect_jobs = jobs[jobs["Match Percentage"] == 100].to_dict(orient="records")

# Suggestions

    suggestions = []
    if missing_skills:
      suggestions.append(f"To excel in {detected_field}, consider adding: {', '.join(missing_skills[:3])}.")
    if score < 50:
          suggestions.append("Try to add more industry-specific keywords and projects.")
    if "experience" not in resume_text_lower:
     suggestions.append("Include a detailed Work Experience section.")

    current_field_skills = field_skills.get(detected_field, [])
    deep_score, breakdown, matched_list = deep_resume_analysis(text, current_field_skills)

    session['score'] = deep_score  
    session['level'] = level
    session['results'] = results_list
    session['breakdown'] = breakdown
    session['matched_skills'] = matched_list 
    session['missing_skills'] = missing_skills
    session['suggestions'] = suggestions
    session['perfect_jobs'] = perfect_jobs
    session['detected_field'] = detected_field
    session['resume_uploaded'] = True

    return redirect('/processing')

  
@app.route('/result')
def result_page():

    if not session.get('resume_uploaded'):
       return redirect('/')

    return render_template(
       'result.html',
    tables=session.get('results'),
    score=session.get('score'),
    level=session.get('level'),
    breakdown=session.get('breakdown', {'tech': 0, 'project_impl': 0, 'exp_match': 0}), # Added this
    missing_skills=session.get('missing_skills'),
    suggestions=session.get('suggestions'),
    perfect_jobs=session.get('perfect_jobs'),
    detected_field=session.get('detected_field')

    )



@app.route('/delete', methods=['POST'])
def delete():

    session.clear()  # sab clear
    return '', 204



@app.route('/download')
def download():

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from flask import send_file

    file_path = "report.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    content = []

    # Title

    content.append(Paragraph("AI Resume Analysis Report", styles['Title']))
    content.append(Spacer(1, 12))

    # Perfect Job Matches

    perfect_jobs = session.get('perfect_jobs', [])
    if perfect_jobs:
        content.append(Paragraph("🏆 Perfect Job Match (100%)", styles['Heading2']))
        for job in perfect_jobs:
            content.append(
               Paragraph(f"{job['job_title']} - {round(job['Match Percentage'], 2)}%", styles['Normal'])

            )
        content.append(Spacer(1, 12))

# Top Job Matches

    results = session.get('results', [])
    if results:

        content.append(Paragraph("💼 Top Job Matches", styles['Heading2']))
        for job in results:
            content.append(
                Paragraph(f"{job['job_title']} - {round(job['Match Percentage'], 2)}%", styles['Normal'])
            )
            content.append(Spacer(1, 12))

# Missing Skills

    missing_skills = session.get('missing_skills', [])
    if missing_skills:
       content.append(Paragraph("❗ Missing Skills", styles['Heading2']))
    for skill in missing_skills:
        content.append(Paragraph(f"- {skill}", styles['Normal']))
        content.append(Spacer(1, 12))



    # JD Match Score

    #jd_score = session.get('jd_score')

    #if jd_score is not None:

    #   content.append(Paragraph("📈 JD Match Score", styles['Heading2']))

    #   content.append(Paragraph(f"{jd_score}%", styles['Normal']))

    #    content.append(Spacer(1, 12))

# Suggestions

    suggestions = session.get('suggestions', [])
    if suggestions:
       content.append(Paragraph("💡 Suggestions", styles['Heading2']))
    for s in suggestions:
        content.append(Paragraph(f"- {s}", styles['Normal']))
        content.append(Spacer(1, 12))

# Build PDF

    doc.build(content)
    return send_file(file_path, as_attachment=True)


def deep_resume_analysis(text, field_skills):
    text_lower = text.lower()

    proj_start = text_lower.find("technical projects")
    if proj_start == -1: proj_start = text_lower.find("projects")

    proj_end = text_lower.find("education")
    if proj_end == -1: proj_end = text_lower.find("key strengths")

    if proj_start != -1:
        if proj_end != -1 and proj_end > proj_start:
            proj_content = text_lower[proj_start:proj_end]
        else:
            proj_content = text_lower[proj_start:]
    else:
        proj_content = ""

    breakdown = {"tech": 0, "project_impl": 0, "exp_match": 0}
    matched_skills = []

   # --- STEP 2: Scoring ---

    for technical_skill in field_skills:
        s = technical_skill.lower().strip()

        if s in text_lower:
            matched_skills.append(s)
            breakdown["tech"] += 1

            if proj_content and s in proj_content:
               breakdown["project_impl"] += 10 # 10 point seedha

    if "experience" in text_lower:
        breakdown["exp_match"] = 10
       
    total_pts = breakdown["tech"] + breakdown["project_impl"] + breakdown["exp_match"]

    max_possible = 100 
    final_score = min((total_pts / max_possible) * 100, 100)

    if breakdown["project_impl"] >= 10:
       breakdown["project_status"] = "Verified ✅"
    else:
       breakdown["project_status"] = "Missing ❌"

    if breakdown["tech"] >= 5:
       breakdown["tech_status"] = "Strong 💪"
    else:
        breakdown["tech_status"] = "Average 💡"

    return round(final_score, 2), breakdown, matched_skills



@app.route('/clear_upload', methods=['POST'])
def clear_upload():
    session.pop('file_name', None)  # Remove uploaded file only
    return '', 204



if __name__ == '__main__':
   app.run(debug=True)