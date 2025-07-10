# src/cmp_copilot/agents/analysis.py

import logging
import json
import os
import csv
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

# --- CORRECTED IMPORTS ---
from .state import AgentState
from ..core.llm import get_llm_client
from ..prompts.system_prompts import AGGREGATE_ANALYSIS_PROMPT, UI_SUMMARY_PROMPT, EMAIL_SUBJECT_PROMPT, EMAIL_BODY_PROMPT
from ..tools.notification_service import send_email
from ..utils.config_loader import load_yaml_config

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _extract_vulnerabilities_from_html(html_content: str) -> List[Dict]:
    """
    Parses the OVAL report HTML to extract details of failed checks (where result is 'true').
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        vulnerabilities = []
        title_header = soup.find('td', class_='TitleLabel', string='OVAL Definition Results')
        if not title_header: return []
        results_table = title_header.find_parent('table')
        if not results_table: return []
        for row in results_table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 5 and cells[1].get_text(strip=True) == 'true':
                vulnerabilities.append({
                    "id": cells[0].get_text(strip=True), "class": cells[2].get_text(strip=True),
                    "references": cells[3].get_text(strip=True).replace('[', '').replace(']', ''),
                    "title": cells[4].get_text(strip=True)
                })
        logging.info(f"Extracted {len(vulnerabilities)} vulnerabilities from the report.")
        return vulnerabilities
    except Exception as e:
        logging.error(f"Error parsing HTML report: {e}", exc_info=True)
        return []

async def analysis_node(state: AgentState) -> Dict:
    """
    This agent node analyzes scan reports, generates a summary for the UI,
    an email report, and a CSV file.
    """
    logging.info("--- ANALYSIS NODE ---")
    messages_to_return: List[Tuple[str, str]] = []
    
    scan_results = state.get('scan_results', [])
    if not scan_results:
        message = "No scan reports were generated. Skipping analysis."
        messages_to_return.append(("system", message))
        return {"final_summary": message, "messages": messages_to_return}

    initial_message = f"🔬 Analyzing {len(scan_results)} scan reports..."
    messages_to_return.append(("system", initial_message))

    llm = get_llm_client()
    all_vulnerabilities = {}
    csv_data = []
    for result in scan_results:
        vm_name = result['vm_name']
        report_path = result['report_path']
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            vulnerabilities = _extract_vulnerabilities_from_html(html_content)
            if vulnerabilities:
                all_vulnerabilities[vm_name] = [v['title'] for v in vulnerabilities]
                for vuln in vulnerabilities:
                    csv_data.append([vm_name, vuln['id'], vuln['title'], vuln['class'], vuln['references']])
        except Exception as e:
            messages_to_return.append(("system", f"⚠️ Error reading report for {vm_name}."))

    if not all_vulnerabilities:
        final_message = "✅ Analysis complete. No critical vulnerabilities found in any of the reports."
        messages_to_return.append(("system", final_message))
        return {"final_summary": final_message, "messages": messages_to_return}

    reports_dir = os.path.dirname(scan_results[0]['report_path'])
    csv_report_path = os.path.join(reports_dir, 'vulnerability_summary.csv')
    try:
        with open(csv_report_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Host', 'OVAL ID', 'Title', 'Class', 'References'])
            writer.writerows(csv_data)
        messages_to_return.append(("system", f"📄 Vulnerability summary saved to: {csv_report_path}"))
    except Exception as e:
        messages_to_return.append(("system", f"⚠️ Failed to create CSV report: {e}"))

    try:
        # Step 1: Create the structured JSON data from the scan results.
        # This prompt now asks for 'overall_summary' and 'vulnerability_details'
        analysis_prompt = AGGREGATE_ANALYSIS_PROMPT.format(scan_results_json=json.dumps(all_vulnerabilities, indent=2))
        logging.info("Invoking LLM to generate structured summary...")
        summary_str = await llm.invoke_chat_completion([{"role": "user", "content": analysis_prompt}], json_mode=True)
        summary_json = json.loads(summary_str)
        
        # Step 2: Generate the detailed email body.
        body_prompt = EMAIL_BODY_PROMPT.format(json_summary=json.dumps(summary_json, indent=2))
        email_body = await llm.invoke_chat_completion([{"role": "user", "content": body_prompt}])

        # Step 3: Generate the separate, concise summary for the UI.
        ui_summary_prompt = UI_SUMMARY_PROMPT.format(json_summary=json.dumps(summary_json, indent=2))
        ui_summary = await llm.invoke_chat_completion([{"role": "user", "content": ui_summary_prompt}])

        # --- FINAL FIX: Use the correct key 'summary_text' for the EMAIL_SUBJECT_PROMPT ---
        # The prompt expects {summary_text}, but our new JSON has {overall_summary}. We map it here.
        subject_prompt = EMAIL_SUBJECT_PROMPT.format(summary_text=summary_json.get('overall_summary', 'Scan Complete'))
        email_subject = await llm.invoke_chat_completion([{"role": "user", "content": subject_prompt}])
        
        src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(src_dir)
        config_path = os.path.join(project_root, 'config', 'notification_config.yaml')
        recipients = load_yaml_config(config_path).get('manager_recipients', [])

        if recipients:
            messages_to_return.append(("system", f"✉️ Sending notification email to: {recipients}"))
            send_email(
                recipient_emails=recipients, subject=email_subject,
                body=email_body, attachment_path=csv_report_path
            )
        else:
            logging.warning("No manager_recipients found in config. Skipping email notification.")
        
        # Return the dedicated UI summary as the final_summary.
        return {
            "final_summary": ui_summary, 
            "email_sent": bool(recipients),
            "messages": messages_to_return
        }

    except Exception as e:
        error_message = f"Analysis: An unexpected error occurred during LLM summary/notification: {e}"
        logging.error(error_message, exc_info=True)
        messages_to_return.append(("system", error_message))
        return {"error_log": [error_message], "messages": messages_to_return}