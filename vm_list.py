import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import subprocess


url = "https://192.168.210.155/api/providers/1000000000026/vms?expand=resources&attributes=name,ipaddresses"
username = "admin"
password = "smartvm"

response = requests.get(url, auth=HTTPBasicAuth(username, password), verify=False)

data = response.json()

resources = data.get("resources", [])

df = pd.DataFrame([
    {
        "name": res.get("name"),
        "ipaddresses": ", ".join(res.get("ipaddresses", []))
    }
    for res in resources
])

df = df[df['name'].str.startswith('kafka-')]

df['username'] = 'root'
df['password'] = 'stackmax'



remote_command = (
    "wget https://security-metadata.canonical.com/oval/com.ubuntu.$(lsb_release -cs).usn.oval.xml.bz2 && "
    "bunzip2 com.ubuntu.$(lsb_release -cs).usn.oval.xml.bz2 && "
    "apt install -y libopenscap8 && "
    f"oscap oval eval --report {ip}_report.html com.ubuntu.$(lsb_release -cs).usn.oval.xml"
)

ssh_command = [
    "sshpass", "-p", pwd,
    "ssh", "-o", "StrictHostKeyChecking=no",
    f"{user}@{ip}",
    remote_command
]

try:
    result = subprocess.run(ssh_command, capture_output=True, text=True, timeout=60)
    return result.stdout, result.stderr
except subprocess.TimeoutExpired:
    return "", f"SSH command to {ip} timed out."
except Exception as e:
    return "", f"SSH command to {ip} failed: {e}"


from bs4 import BeautifulSoup
import pandas as pd
import os


with open(file_path, "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

rows = soup.find_all("tr")
data = []
for row in rows:
    columns = row.find_all("td")
    if len(columns) >= 5:
        result = columns[1].get_text(strip=True)
        title = columns[4].get_text(strip=True)
        if result.lower() == "true":
            data.append({"Result": result, "Title": title})

df = pd.DataFrame(data)

#=================================================================
vm list :

             name      ipaddresses username  password
15        kafka-2  192.168.190.185     root  stackmax
16        kafka-3  192.168.190.181     root  stackmax
23        kafka-1  192.168.190.171     root  stackmax
24        kafka-3  192.168.190.159     root  stackmax
25        kafka-2  192.168.190.189     root  stackmax
44    kafka-con-1  192.168.190.170     root  stackmax
45    kafka-con-2  192.168.190.141     root  stackmax
46        kafka-1  192.168.190.175     root  stackmax
47  kafka-connect  192.168.190.158     root  stackmax