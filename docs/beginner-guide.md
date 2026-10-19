# Beginner guide: never used Ansible? Start here

This page takes you from "what is Ansible" to a running database. No prior
Ansible knowledge assumed. If you already know Ansible, skip to the
[README](../README.md).

## What Ansible is, in 30 seconds

Ansible is a tool that configures servers for you over SSH. You write what
you want (in files), Ansible logs into each server and makes it so. You run
everything from your own laptop; nothing needs to be installed on the servers
except SSH and sudo, which Ubuntu already has.

Five words you will see everywhere:

| Word | Meaning |
|---|---|
| Control node | Your laptop. Ansible runs here. |
| Inventory | A file listing your servers and their IP addresses. |
| Playbook | A file describing the steps to run, in order. |
| Role | A reusable bundle of steps (for example, "install MySQL"). |
| Vault | An encrypted file holding passwords. You unlock it with one password. |

## What you need

- Your laptop (Linux or macOS; Windows works through WSL).
- Your servers: fresh Ubuntu 24.04, reachable over the network.
- An SSH key. If you do not have one: `ssh-keygen -t ed25519`, then `ssh-copy-id ubuntu@<server-ip>` for each server. Test with `ssh ubuntu@<server-ip>`; it should log you in without asking for a password.

## 1. Install Ansible

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y ansible

# or any system with Python
pip install ansible-core
```

Check it: `ansible --version` should show 2.16 or newer.

## 2. Get this project

```bash
git clone https://github.com/OT-OSM/percona_server.git
cd percona_server
git checkout percona_replication_setup_8.4
ansible-galaxy collection install -r requirements.yml
```

The last command downloads two helper libraries the project needs. Run it once.

## 3. Tell Ansible about your servers

Open `inventories/lab/ha-4server.yml` (or `ha.yml` for five servers) and
replace the example IPs with your real server IPs. That file is the
inventory. Nothing else in it needs to change for a first run.

Check Ansible can reach everything:

```bash
ansible -i inventories/lab/ha-4server.yml all -m ping
```

Every server should answer `pong`. If one does not, the IP is wrong or your
SSH key is missing there; fix that before continuing.

## 4. Set the passwords

```bash
ansible-vault create inventories/lab/group_vars/all/vault.yml
```

An editor opens. Copy the key names from
`inventories/lab/group_vars/all/vault.example.yml` and invent a password for
each. Save and close. The file is encrypted; only someone with the vault
password can read it. You will type that vault password whenever you see
`--ask-vault-pass` in a command below.

Also generate one ID for your database group and put it in
`inventories/lab/group_vars/all/main.yml` as `percona_group_name`:

```bash
python3 -c 'import uuid; print(uuid.uuid4())'
```

## 5. Run it

Three commands, in order. The first two are safety nets; the third does the
real work.

```bash
# 1. Checks everything before touching a server. Fix what it complains about.
ansible-playbook -i inventories/lab/ha-4server.yml playbooks/preflight.yml --ask-vault-pass

# 2. Installs Percona, forms the database group, sets up routing, backups, monitoring.
ansible-playbook -i inventories/lab/ha-4server.yml playbooks/ha.yml --ask-vault-pass

# 3. Verifies the result end to end.
ansible-playbook -i inventories/lab/ha-4server.yml playbooks/verify.yml --ask-vault-pass
```

The middle command takes several minutes (it downloads and installs database
software). Do not stop it halfway; if it fails, read the error and continue
to the next section.

## 6. How to read the output

- Green `ok`: nothing needed doing.
- Yellow `changed`: Ansible changed something on the server. Normal on first run.
- Red `failed`: a step failed. The error message names the task and the server. Scroll up to the first red block; everything after it is just fallout.
- `PLAY RECAP` at the end summarizes per server. Zero `failed` means success.

## When something fails

1. Read the first red error, slowly. It usually says exactly what is wrong ("could not reach host", "wrong password", "disk full").
2. Fix the cause (often a typo in an IP or a missed vault key), then run the same command again. Ansible skips what already worked.
3. If the error is about the database itself, open `docs/troubleshooting.md` and find your symptom.
4. Still stuck? Copy the full red block and ask someone who knows the setup; the error text is everything they need.

## What to read next

- `LOCAL-RUN.md`: the same steps with exact verification queries and a failover drill.
- `docs/operations.md`: daily procedures (health checks, failover, restore, backups).
- `docs/production-checklist.md`: decisions to make before a client deploy.
- `docs/migrate-standalone-to-gr.md`: turning a standalone server into a group later.
