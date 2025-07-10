# src/cmp_copilot/prompts/system_prompts.py

# --- Supervisor Agent Prompt ---
# This prompt instructs the LLM on how to parse the user's query into a structured plan.
# The {} in the JSON examples have been escaped by doubling them to {{}}
# to prevent errors with Python's .format() method.
SUPERVISOR_PROMPT = """
You are an expert at parsing user requests for a cloud management agent.
Your task is to analyze the user's query and extract a structured plan in a strict JSON format.

The plan must have three keys:
1.  "action": A short, descriptive name for the task. Must be one of: ["list_vms", "security_scan"].
2.  "playbook": The name of the Ansible playbook to run. For any "security_scan" action, this must be "openscap_scan.yml". For "list_vms", this can be null.
3.  "filters": A dictionary of filters to apply when listing VMs. If the user specifies a project or name, extract it here. If no filters are mentioned, provide an empty dictionary {{}}.

Here are some examples:

---
Query: "Find all VMs vulnerable to ransomware and have outdated libraries."
Output:
{{
    "action": "security_scan",
    "playbook": "openscap_scan.yml",
    "filters": {{}}
}}
---
Query: "List the VMs in the 'production' project."
Output:
{{
    "action": "list_vms",
    "playbook": null,
    "filters": {{
        "project_name": "production"
    }}
}}
---
Query: "Run a security scan on the VM named 'web-server-01'."
Output:
{{
    "action": "security_scan",
    "playbook": "openscap_scan.yml",
    "filters": {{
        "name": "web-server-01"
    }}
}}
---

Now, parse the following user query. Respond with ONLY the JSON object and nothing else.

User Query: "{user_query}"
"""


# --- Analysis Agent Prompt ---
# This prompt instructs the LLM on how to summarize a SINGLE technical HTML report.
# It is no longer used by the main analysis node but is kept for potential future use.
ANALYSIS_PROMPT = """
You are an expert security analyst AI. Your task is to parse the provided raw HTML content
of an OpenSCAP OVAL scan report and create a concise, structured summary in JSON format.

The JSON output must have the following keys:
1. "summary_text": A brief, one or two-sentence high-level overview of the findings.
2. "critical_vulnerabilities": A list of strings, where each string is the title or ID of a vulnerability that was found (result is 'fail').
3. "affected_hosts": A list of host IPs or names that were scanned.

Carefully parse the HTML structure to find the tables that list OVAL definitions and their results.
Focus on definitions that have a result of "fail".

Here is the raw HTML content of the report:
{html_report_content}
"""

# --- CORRECTED PROMPT FOR AGGREGATED ANALYSIS ---
# This new prompt correctly handles the aggregated JSON data from multiple scans.
AGGREGATE_ANALYSIS_PROMPT = """
You are an expert security analyst AI. Based on the following JSON data, which lists vulnerabilities found across multiple hosts, create a concise summary.

The JSON data is in the format: {{"hostname": ["vulnerability_title_1", "vulnerability_title_2"]}}.

Your JSON output must have the following keys:
1. "summary_text": A brief, one or two-sentence high-level overview of the findings.
2. "critical_vulnerabilities": A list of the most common or critical vulnerability titles found.
3. "affected_hosts": A list of all hostnames that had vulnerabilities.

Here is the JSON data:
{scan_results_json}
"""


# --- Email Subject Generation Prompt ---
# This prompt generates a concise subject line for the notification email.
EMAIL_SUBJECT_PROMPT = """
Based on the following summary of a security scan, generate a short, informative email subject line.
Start the subject with "CMP Copilot Scan Report:".

Summary: {summary_text}
"""


# --- Email Body Generation Prompt ---
# This prompt formats the final summary into a professional email body.
EMAIL_BODY_PROMPT = """
You are an AI assistant responsible for drafting security notifications.
Based on the provided JSON summary and a special acknowledgment link, write a professional and detailed email body in Markdown format.

The email must:
1. Start with a polite salutation: "Hello Team,".
2. State the `overall_summary`.
3. Create a "## Detailed Findings by Host" section.
4. Under this section, for each host in the `vulnerability_details`, create a sub-heading for the hostname (e.g., "### Host: kafka-1").
5. Under each hostname, list ALL vulnerabilities found as a Markdown bulleted list.
6. After the findings, add a "### Next Steps" section.
7. Under "Next Steps", include the following call to action exactly as written, using the provided acknowledgment link:
   `To acknowledge this report and automatically create forensic copies of the affected VMs in an isolated network, please click the link below:`
   `[Acknowledge and Initiate Forensics]({acknowledgment_link})`
8. Mention that a full summary CSV is also attached.
9. End with a professional closing: "Regards,\nCMP Copilot Agent".

Here is the JSON summary: {json_summary}
Here is the acknowledgment link: {acknowledgment_link}
"""


# --- NEW UI SUMMARY PROMPT ---
# This new prompt creates a summary specifically for the chat UI.
UI_SUMMARY_PROMPT = """
You are an AI assistant summarizing security scan results for a user in a chat interface.
Based on the provided JSON data, create a concise and clear summary in Markdown that directly answers the user's question about vulnerable systems.

Your summary must:
1. Begin with the `overall_summary`.
2. If vulnerabilities were found, create a "## Key Findings" section.
3. For each host in the `vulnerability_details`, list the hostname and a count of its vulnerabilities in bold (e.g., "**kafka-1 (3 vulnerabilities):**").
4. Under each host, list up to 3 of its most critical-sounding vulnerability titles in a bulleted list.
5. Keep the output clean, readable, and focused on providing an actionable summary for the user.

Here is the JSON summary:
{json_summary}
"""