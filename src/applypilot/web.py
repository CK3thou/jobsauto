"""Local browser dashboard for reviewing discovered jobs."""

from __future__ import annotations

import json
import ipaddress
import os
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from applypilot.config import PROFILE_PATH, load_env, load_profile
from applypilot.database import get_connection, get_stats, init_db

_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ApplyPilot</title>
<style>
:root{color-scheme:dark;--bg:#0b1220;--panel:#111c2f;--line:#24334c;--text:#e5edf8;--muted:#91a2bc;--blue:#69a7ff;--green:#42d392}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}
main{max-width:1180px;margin:auto;padding:36px 22px 64px}header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:26px}
h1{font-size:30px;margin:0}header p{margin:4px 0;color:var(--muted)}button,input,select{font:inherit;color:var(--text);background:#17243a;border:1px solid var(--line);border-radius:8px;padding:10px 12px}
button{cursor:pointer}button:hover{border-color:var(--blue)}.refresh{color:var(--blue)}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:22px}.stat,.toolbar,.job{background:var(--panel);border:1px solid var(--line);border-radius:12px}
.stat{padding:18px}.stat b{display:block;font-size:26px}.stat span,.muted{color:var(--muted)}
.toolbar{display:flex;gap:10px;padding:14px;margin-bottom:14px}.toolbar input{flex:1;min-width:150px}.toolbar select{min-width:145px}
#jobs{display:grid;gap:12px}.job{padding:18px;display:grid;grid-template-columns:1fr auto;gap:12px}.job h2{font-size:17px;margin:0 0 4px}.job a{color:var(--text);text-decoration:none}.job a:hover{color:var(--blue)}
.meta{display:flex;gap:8px;flex-wrap:wrap;color:var(--muted);font-size:13px}.score{color:var(--green);font-weight:700}.actions{display:flex;align-items:start;gap:10px}.apply{color:var(--blue);text-decoration:none;border:1px solid var(--line);border-radius:7px;padding:7px 10px}
.empty{padding:28px;border:1px dashed var(--line);border-radius:12px;text-align:center;color:var(--muted)}#message{min-height:22px;color:var(--muted);margin:14px 0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;margin:18px 0}
.panel h2{margin:0 0 6px}.panel p{color:var(--muted);margin:4px 0 14px}
.profile-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.profile-grid label{display:grid;gap:4px;color:var(--muted);font-size:13px}
.profile-grid input,.profile-grid textarea{width:100%}.profile-grid textarea{min-height:70px}
.profile-grid .wide{grid-column:1/-1}.check{display:flex!important;align-items:center;gap:8px}.check input{width:auto}
.job-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.interested{color:var(--green)}.posting{color:var(--blue);text-decoration:none;border:1px solid var(--line);border-radius:7px;padding:7px 10px}
@media(max-width:700px){main{padding:24px 14px}.stats{grid-template-columns:repeat(2,minmax(0,1fr))}header{align-items:flex-start}.toolbar{flex-direction:column}.job{grid-template-columns:1fr}.actions{justify-content:space-between}}
@media(max-width:800px){.profile-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
</head>
<body><main>
<header><div><h1>ApplyPilot</h1><p>Jobs posted in the last 3 days · refreshed from your local database</p></div><button class="refresh" id="refresh">Refresh</button></header>
<details class="panel" id="profile-panel" open>
<summary><strong>Application profile</strong> <span class="muted">Review these details before preparing applications</span></summary>
<p>These details are saved locally on this computer and used to prepare applications. Some setup answers may be unconfirmed; verify your work authorization and sponsorship answers. ApplyPilot will not submit applications automatically.</p>
<form id="profile-form">
<div class="profile-grid">
<label>Full name<input name="full_name" autocomplete="name"></label>
<label>Preferred name<input name="preferred_name"></label>
<label>Email<input name="email" type="email" autocomplete="email"></label>
<label>Phone<input name="phone" autocomplete="tel"></label>
<label>City<input name="city" autocomplete="address-level2"></label>
<label>Province / state<input name="province_state"></label>
<label>Country<input name="country" autocomplete="country-name"></label>
<label>Postal code<input name="postal_code" autocomplete="postal-code"></label>
<label>LinkedIn URL<input name="linkedin_url"></label>
<label>GitHub URL<input name="github_url"></label>
<label>Portfolio URL<input name="portfolio_url"></label>
<label>Website URL<input name="website_url"></label>
<label>Current title<input name="current_title"></label>
<label>Years of experience<input name="years_of_experience_total"></label>
<label>Education level<input name="education_level"></label>
<label class="wide">Target roles<input name="target_role"></label>
<label>Programming languages<input name="programming_languages"></label>
<label>Frameworks<input name="frameworks"></label>
<label>Tools<input name="tools"></label>
<label class="wide">Preserved companies (comma-separated)<input name="preserved_companies"></label>
<label class="wide">Preserved projects (comma-separated)<input name="preserved_projects"></label>
<label>School / institution<input name="preserved_school"></label>
<label class="wide">Real metrics (comma-separated)<input name="real_metrics"></label>
<label>Salary expectation<input name="salary_expectation"></label>
<label>Salary currency<input name="salary_currency"></label>
<label>Earliest start date<input name="earliest_start_date"></label>
<label>Work permit type<input name="work_permit_type"></label>
<label class="check"><input name="legally_authorized_to_work" type="checkbox"> Legally authorized to work</label>
<label class="check"><input name="require_sponsorship" type="checkbox"> Require sponsorship</label>
<label>Gender (optional)<input name="gender"></label>
<label>Race / ethnicity (optional)<input name="race_ethnicity"></label>
<label>Veteran status (optional)<input name="veteran_status"></label>
<label>Disability status (optional)<input name="disability_status"></label>
</div>
<p id="profile-message" role="status"></p><button type="submit">Save profile</button>
</form></details>
<section class="stats" aria-label="Pipeline summary">
<div class="stat"><b id="total">—</b><span>Recent jobs</span></div>
<div class="stat"><b id="scored">—</b><span>Recent jobs scored</span></div>
<div class="stat"><b id="strong">—</b><span>Strong recent matches (7+)</span></div>
<div class="stat"><b id="ready">—</b><span>Recent jobs ready to apply</span></div>
</section>
<section class="toolbar" aria-label="Job filters">
<input id="search" type="search" placeholder="Search title, employer, or location" aria-label="Search jobs">
<select id="min-score" aria-label="Minimum score"><option value="0">All scores</option><option value="5">Score 5+</option><option value="7">Score 7+</option><option value="8">Score 8+</option></select>
<select id="status" aria-label="Job status"><option value="all">All jobs</option><option value="scored">Scored</option><option value="interested">Interested</option><option value="ready">Ready to apply</option></select>
</section>
<div id="message" role="status"></div><section id="jobs" aria-live="polite"></section>
</main>
<script>
const state={jobs:[]};
const el=(id)=>document.getElementById(id);
function render(){
 const query=el('search').value.trim().toLowerCase(), min=Number(el('min-score').value), status=el('status').value;
 const matches=state.jobs.filter(j=>(j.fit_score||0)>=min&&(!query||`${j.title} ${j.site} ${j.location}`.toLowerCase().includes(query))&&(status==='all'||(status==='scored'?j.fit_score!==null:status==='interested'?j.review_status==='interested':j.ready)));
 el('message').textContent=`Showing ${matches.length} of ${state.jobs.length} jobs`;
 const container=el('jobs'); container.replaceChildren();
 if(!matches.length){const empty=document.createElement('div');empty.className='empty';empty.textContent='No matching jobs. Run the pipeline to discover more jobs or adjust your filters.';container.append(empty);return}
 for(const j of matches){
  const card=document.createElement('article');card.className='job';
  const details=document.createElement('div'), title=document.createElement('h2'), link=document.createElement('a');
  link.textContent=j.title||'Untitled role';link.href=j.url;link.target='_blank';link.rel='noopener noreferrer';title.append(link);
  const meta=document.createElement('div');meta.className='meta';
  const parts=[j.site,j.location,j.salary,j.posted_at?`Posted ${new Date(j.posted_at).toLocaleString()}`:''].filter(Boolean);if(j.fit_score!==null)parts.push(`Fit ${j.fit_score}/10`);
  meta.textContent=parts.join(' · ');details.append(title,meta);
  if(j.reasoning){const reason=document.createElement('p');reason.className='muted';reason.textContent=j.reasoning;details.append(reason)}
  const actions=document.createElement('div');actions.className='actions';
  const actionList=document.createElement('div');actionList.className='job-actions';
  const interested=document.createElement('button');interested.className=j.review_status==='interested'?'interested':'';interested.textContent=j.review_status==='interested'?'Interested ✓':'Add to shortlist';
  interested.addEventListener('click',()=>setReview(j,j.review_status==='interested'?'unreviewed':'interested'));actionList.append(interested);
  const posting=document.createElement('a');posting.className='posting';posting.textContent='View posting';posting.href=j.application_url||j.url;posting.target='_blank';posting.rel='noopener noreferrer';actionList.append(posting);
  if(j.ready){const apply=document.createElement('a');apply.className='apply';apply.textContent='Apply';apply.href=j.application_url||j.url;apply.target='_blank';apply.rel='noopener noreferrer';actions.append(apply)}
  actions.append(actionList);card.append(details,actions);container.append(card);
 }
}
function setFormValue(form,name,value){const input=form.elements.namedItem(name);if(!input)return;if(input.type==='checkbox')input.checked=Boolean(value);else input.value=Array.isArray(value)?value.join(', '):(value||'')}
function profilePayload(form){
 const value=(name)=>form.elements.namedItem(name).value.trim();
 const list=(name)=>value(name).split(',').map(x=>x.trim()).filter(Boolean);
 return {
  personal:{full_name:value('full_name'),preferred_name:value('preferred_name'),email:value('email'),phone:value('phone'),city:value('city'),province_state:value('province_state'),country:value('country'),postal_code:value('postal_code'),linkedin_url:value('linkedin_url'),github_url:value('github_url'),portfolio_url:value('portfolio_url'),website_url:value('website_url')},
  experience:{current_title:value('current_title'),years_of_experience_total:value('years_of_experience_total'),education_level:value('education_level'),target_role:value('target_role')},
  skills_boundary:{programming_languages:list('programming_languages'),frameworks:list('frameworks'),tools:list('tools')},
  resume_facts:{preserved_companies:list('preserved_companies'),preserved_projects:list('preserved_projects'),preserved_school:value('preserved_school'),real_metrics:list('real_metrics')},
  work_authorization:{legally_authorized_to_work:form.elements.namedItem('legally_authorized_to_work').checked,require_sponsorship:form.elements.namedItem('require_sponsorship').checked,work_permit_type:value('work_permit_type')},
  compensation:{salary_expectation:value('salary_expectation'),salary_currency:value('salary_currency')},
  availability:{earliest_start_date:value('earliest_start_date')},
  eeo_voluntary:{gender:value('gender'),race_ethnicity:value('race_ethnicity'),veteran_status:value('veteran_status'),disability_status:value('disability_status')}
 }
}
async function loadProfile(){
 const response=await fetch('/api/profile');if(!response.ok)throw new Error(`Request failed (${response.status})`);
 const p=await response.json(),form=el('profile-form');
 const fields={...p.personal,...p.experience,...p.work_authorization,...p.compensation,...p.availability,...p.eeo_voluntary};
 for(const name of ['programming_languages','frameworks','tools'])fields[name]=p.skills_boundary?.[name]||[];
 for(const name of ['preserved_companies','preserved_projects','real_metrics'])fields[name]=p.resume_facts?.[name]||[];
 fields.preserved_school=p.resume_facts?.preserved_school||'';
 for(const [name,value] of Object.entries(fields))setFormValue(form,name,value);
}
async function saveProfile(event){
 event.preventDefault();const message=el('profile-message');message.textContent='Saving…';
 try{const response=await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(profilePayload(el('profile-form')))});
  const result=await response.json();if(!response.ok)throw new Error(result.error||`Request failed (${response.status})`);message.textContent='Profile saved locally.';
 }catch(error){message.textContent=`Could not save profile: ${error.message}`}
}
async function setReview(job,review_status){
 el('message').textContent='Saving shortlist choice…';
 try{const response=await fetch('/api/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:job.url,review_status})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||`Request failed (${response.status})`);job.review_status=result.review_status;render();
 }catch(error){el('message').textContent=`Could not save choice: ${error.message}`}
}
async function refresh(){
 el('message').textContent='Loading jobs…';
 try{const response=await fetch('/api/dashboard');if(!response.ok)throw new Error(`Request failed (${response.status})`);const data=await response.json();state.jobs=data.jobs;
  for(const [id,value] of Object.entries(data.stats))el(id).textContent=value.toLocaleString();
  render();
 }catch(error){el('message').textContent=`Could not load dashboard: ${error.message}`}
}
el('refresh').addEventListener('click',refresh);el('search').addEventListener('input',render);el('min-score').addEventListener('change',render);el('status').addEventListener('change',render);el('profile-form').addEventListener('submit',saveProfile);
loadProfile().catch(error=>el('profile-message').textContent=`Could not load profile: ${error.message}`);refresh();
</script></body></html>"""


def _dashboard_data() -> dict:
    conn = get_connection()
    stats = get_stats(conn)
    jobs = conn.execute(
        """
        SELECT url, title, site, location, salary, application_url,
               fit_score, score_reasoning, tailored_resume_path, applied_at,
               review_status, posted_at
        FROM jobs
        WHERE posted_at >= ? AND posted_at <= ?
        ORDER BY COALESCE(fit_score, 0) DESC, posted_at DESC
        LIMIT 1000
        """,
        (
            (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            datetime.now(timezone.utc).isoformat(),
        ),
    ).fetchall()
    rows = []
    for row in jobs:
        reasoning = (row["score_reasoning"] or "").splitlines()
        rows.append({
            "url": row["url"],
            "title": row["title"] or "Untitled role",
            "site": row["site"] or "",
            "location": row["location"] or "",
            "salary": row["salary"] or "",
            "application_url": row["application_url"] or "",
            "fit_score": row["fit_score"],
            "reasoning": reasoning[-1] if len(reasoning) > 1 else "",
            "ready": bool(row["tailored_resume_path"] and row["application_url"] and not row["applied_at"]),
            "review_status": row["review_status"] or "unreviewed",
            "posted_at": row["posted_at"],
        })
    return {
        "stats": {
            "total": len(rows),
            "scored": sum(row["fit_score"] is not None for row in rows),
            "strong": sum((row["fit_score"] or 0) >= 7 for row in rows),
            "ready": sum(row["ready"] for row in rows),
        },
        "jobs": rows,
    }


def _update_profile(updates: dict) -> None:
    allowed_fields = {
        "personal": {
            "full_name", "preferred_name", "email", "phone", "city", "province_state",
            "country", "postal_code", "linkedin_url", "github_url", "portfolio_url", "website_url",
        },
        "experience": {"current_title", "years_of_experience_total", "education_level", "target_role"},
        "skills_boundary": {"programming_languages", "frameworks", "tools"},
        "resume_facts": {"preserved_companies", "preserved_projects", "preserved_school", "real_metrics"},
        "work_authorization": {"legally_authorized_to_work", "require_sponsorship", "work_permit_type"},
        "compensation": {"salary_expectation", "salary_currency"},
        "availability": {"earliest_start_date"},
        "eeo_voluntary": {"gender", "race_ethnicity", "veteran_status", "disability_status"},
    }
    if not isinstance(updates, dict):
        raise ValueError("Profile data must be a JSON object.")

    profile = load_profile()
    for section, values in updates.items():
        if section not in allowed_fields or not isinstance(values, dict):
            raise ValueError(f"Invalid profile section: {section}")
        current = profile.setdefault(section, {})
        for key, value in values.items():
            if key not in allowed_fields[section]:
                raise ValueError(f"Invalid profile field: {key}")
            if key in {"legally_authorized_to_work", "require_sponsorship"}:
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be true or false.")
                current[key] = value
            elif key in {
                "programming_languages", "frameworks", "tools",
                "preserved_companies", "preserved_projects", "real_metrics",
            }:
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise ValueError(f"{key} must be a list of strings.")
                current[key] = [item.strip() for item in value if item.strip()]
            elif isinstance(value, str) and len(value) <= 1000:
                current[key] = value.strip()
            else:
                raise ValueError(f"{key} must be text with at most 1000 characters.")

    temp_path = PROFILE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp_path, PROFILE_PATH)


class _DashboardHandler(BaseHTTPRequestHandler):
    def _is_local_request(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc
        if length <= 0 or length > 65536:
            raise ValueError("Request body must be between 1 and 65536 bytes.")
        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must contain valid JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/profile" and not self._is_local_request():
            self.send_error(403)
            return
        if path == "/":
            body = _HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif path == "/api/dashboard":
            body = json.dumps(_dashboard_data()).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif path == "/api/profile":
            profile = load_profile()
            profile.get("personal", {}).pop("password", None)
            body = json.dumps(profile).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if not self._is_local_request():
            self.send_error(403)
            return
        path = urlparse(self.path).path
        if path not in {"/api/profile", "/api/review"}:
            self.send_error(404)
            return
        try:
            payload = self._json_body()
            if path == "/api/profile":
                _update_profile(payload)
                self._send_json(200, {"saved": True})
                return

            url = payload.get("url")
            review_status = payload.get("review_status")
            if (
                not isinstance(url, str)
                or not url
                or not isinstance(review_status, str)
                or review_status not in {"unreviewed", "interested", "skipped"}
            ):
                raise ValueError("A job URL and valid review status are required.")
            conn = get_connection()
            cursor = conn.execute(
                "UPDATE jobs SET review_status = ? WHERE url = ?",
                (review_status, url),
            )
            conn.commit()
            if cursor.rowcount == 0:
                self._send_json(404, {"error": "Job not found."})
                return
            self._send_json(200, {"review_status": review_status})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except OSError as exc:
            self._send_json(500, {"error": f"Could not save local profile: {exc}"})

    def log_message(self, format: str, *args) -> None:
        return


def serve_dashboard(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Serve the live dashboard on localhost until interrupted."""
    load_env()
    init_db()
    server = ThreadingHTTPServer((host, port), _DashboardHandler)
    url = f"http://{host}:{port}"
    print(f"ApplyPilot dashboard: {url} (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ApplyPilot dashboard.")
    finally:
        server.server_close()
