#!/usr/bin/env python3
"""Local validation only: no live hosts, package installation or database mutations."""
from pathlib import Path
import base64
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
ENV = dict(os.environ, ANSIBLE_LOCAL_TEMP='/tmp/percona-test-ansible',
           ANSIBLE_REMOTE_TEMP='/tmp/percona-test-remote',
           ANSIBLE_GALAXY_CACHE_DIR='/tmp/percona-test-galaxy')


def run(command, expected=0):
    result = subprocess.run(command, env=ENV, capture_output=True, text=True)
    if result.returncode != expected:
        print(result.stdout, result.stderr)
        raise AssertionError('Unexpected result: ' + ' '.join(command))
    return result


def main():
    yaml_files = [*ROOT.glob('*.yml'), *ROOT.glob('roles/**/*.yml'),
                  *ROOT.glob('playbooks/*.yml'), *ROOT.glob('inventories/**/*.yml')]
    for path in yaml_files:
        yaml.safe_load(path.read_text()) if path.name != 'vault.yml' else None
    print(f'YAML parsed: {len(yaml_files)} files')
    for role in (ROOT/'roles').iterdir():
        assert (role/'tasks/preflight.yml').exists(), role
        assert (role/'tasks/validation.yml').exists(), role
        assert '```mermaid' in (role/'README.md').read_text(), role
    print('All six roles have preflight, validation and a component diagram')
    for path in sorted((ROOT/'playbooks').glob('*.yml')):
        run(['ansible-playbook', '-i', str(ROOT/'tests/inventory.yml'), str(path), '--syntax-check'])
    print('Playbook syntax: 10 passed')
    check_module_parameters()
    run(['python3','-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
    print('Backup failure-path tests: passed')
    with tempfile.TemporaryDirectory(prefix='percona-render-') as temporary:
        temp = Path(temporary)
        tasks = []
        for role in sorted((ROOT/'roles').iterdir()):
            defaults = yaml.safe_load((role/'defaults/main.yml').read_text())
            for src in sorted((role/'templates').glob('*.j2')):
                variables = copy.deepcopy(defaults)
                variables.update({'percona_root_password':'fixture-only-password',
                                  'exporter_db_password':'fixture "quote" \\ slash é',
                                  'backup_db_password':'fixture "quote" \\ slash é',
                                  'orchestrator_db_password':'fixture "quote" \\ slash',
                                  'orchestrator_http_password':'fixture-http-password',
                                  'proxysql_admin_password':'fixture-proxy-password'})
                tasks.append({'name':f'Render {role.name}/{src.name}',
                              'ansible.builtin.template':{'src':str(src),'dest':str(temp/(role.name+'-'+src.name[:-3]))},
                              'vars':variables})
        # Exercise boolean/string escaping in both orchestration modes.
        orc = yaml.safe_load((ROOT/'roles/orchestrator/defaults/main.yml').read_text())
        orc.update({'orchestrator_recovery_enabled':True,'orchestrator_recovery_filters':['cluster-name'],
                    'orchestrator_fencing_hook':'/opt/hooks/fence','orchestrator_routing_hook':'/opt/hooks/route'})
        tasks.append({'name':'Render explicit recovery','ansible.builtin.template':{
            'src':str(ROOT/'roles/orchestrator/templates/orchestrator.conf.json.j2'),
            'dest':str(temp/'recovery.json')},'vars':orc})
        play=temp/'render.yml'
        play.write_text(yaml.safe_dump([{'hosts':'localhost','gather_facts':False,'tasks':tasks}],sort_keys=False))
        run(['ansible-playbook','-i','localhost,','-c','local',str(play)])
        disabled=json.loads((temp/'orchestrator-orchestrator.conf.json').read_text())
        enabled=json.loads((temp/'recovery.json').read_text())
        assert disabled['RecoveryEnabled'] is False
        assert disabled['RecoverMasterClusterFilters'] == []
        assert disabled['PreFailoverProcesses'] == [] and disabled['PostMasterFailoverProcesses'] == []
        assert enabled['PreFailoverProcesses'] == ['/opt/hooks/fence {failedHost}']
        assert enabled['PostMasterFailoverProcesses'] == ['/opt/hooks/route {failedHost} {successorHost}']
        assert disabled['MySQLTopologyPassword'] == 'fixture "quote" \\ slash'
        for p in temp.glob('*.json'): json.loads(p.read_text())
        server=(temp/'percona_server-mysqld.cnf').read_text()
        assert 'binlog_do_db' not in server and 'binlog_ignore_db' not in server
        assert 'gtid-mode = ON' in server and 'super-read-only = OFF' in server
        print(f'Template rendering: {len(tasks)} variants passed; JSON and default recovery guards verified')
        check_guards(temp)
        check_memory_sizing(temp)
    check_links()
    print('PASS: local validation completed; no live deployment was attempted')


def check_memory_sizing(temp):
    defaults = yaml.safe_load((ROOT/'roles/percona_server/defaults/main.yml').read_text())
    guard = next(task['ansible.builtin.assert'] for task in
                 yaml.safe_load((ROOT/'roles/percona_server/tasks/preflight.yml').read_text())
                 if task['name'] == 'Validate memory sizing inputs')
    cases = [
        ('2g', {'ansible_facts': {'memtotal_mb': 2048}}, '1024M', 150),
        ('4g', {'ansible_facts': {'memtotal_mb': 4096}}, '2048M', 150),
        ('8g', {'ansible_facts': {'memtotal_mb': 8192}}, '4096M', 150),
        ('16g', {'ansible_facts': {'memtotal_mb': 16384}}, '8192M', 150),
        ('missing-facts', {}, '512M', 150),
        ('minimum-pool', {'percona_memory_mb': 512, 'percona_buffer_pool_percent': 10}, '128M', 150),
        ('dedicated', {'percona_memory_mb': 8192, 'percona_buffer_pool_percent': 70}, '5120M', 150),
        ('small-dedicated', {'percona_memory_mb': 2048, 'percona_buffer_pool_percent': 70}, '1024M', 150),
        ('explicit', {'percona_innodb_buffer_pool_size': '4G', 'percona_max_connections': 100}, '4G', 100),
        ('limited-budget', {'ansible_facts': {'memtotal_mb': 16384}, 'percona_memory_mb': 4096}, '2048M', 150),
    ]
    plays = []
    for name, overrides, _, _ in cases:
        variables = dict(defaults, ansible_facts={})
        variables.update(overrides)
        plays.append({'name': name, 'hosts': 'localhost', 'gather_facts': False,
                      'vars': variables, 'tasks': [
                          {'name': 'Validate sizing', 'ansible.builtin.assert': guard},
                          {'name': 'Render actual server config', 'ansible.builtin.template': {
                              'src': str(ROOT/'roles/percona_server/templates/mysqld.cnf.j2'),
                              'dest': str(temp/f'memory-{name}.cnf')}}]})
    for overrides in [{'percona_memory_mb': 0}, {'percona_memory_mb': 'invalid'},
                      {'percona_buffer_pool_percent': 100}, {'percona_max_connections': 0}]:
        variables = dict(defaults, ansible_facts={})
        variables.update(overrides)
        plays.append({'hosts': 'localhost', 'gather_facts': False, 'vars': variables, 'tasks': [
            {'name': 'Reject invalid sizing', 'ansible.builtin.assert': guard,
             'register': 'sizing_result', 'ignore_errors': True},
            {'name': 'Require rejection', 'ansible.builtin.assert': {'that': ['sizing_result is failed']}}]})
    path = temp/'memory-sizing.yml'
    path.write_text(yaml.safe_dump(plays, sort_keys=False))
    run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(path)])
    for name, _, pool, connections in cases:
        config = (temp/f'memory-{name}.cnf').read_text()
        assert f'innodb-buffer-pool-size = {pool}\n' in config, name
        assert f'max-connections = {connections}\n' in config, name
    print('Memory sizing: 10 rendered configurations and 4 invalid-input guards passed')


def check_guards(temp):
    def pick(file, name):
        return next(t for t in yaml.safe_load((ROOT/file).read_text()) if t['name']==name)['ansible.builtin.assert']
    guards = []
    source_assert = pick('roles/percona_replication/tasks/configure.yml','Never silently change an existing source')
    common={'percona_primary':'db1','hostvars':{'db1':{'percona_address':'192.0.2.11'}},'percona_replica_seeded':True,
            'replication_existing':{'Is_Replica':True,'Source_Host':'192.0.2.11','Auto_Position':1}}
    # hostvars is an Ansible special variable, so insert db1 into the test inventory instead.
    common.pop('hostvars')
    guards.append(('existing matching source',source_assert,common,True))
    mismatch=copy.deepcopy(common);mismatch['replication_existing']['Source_Host']='192.0.2.99'
    guards.append(('reject different source',source_assert,mismatch,False))
    unseeded={'percona_primary':'db1','percona_replica_seeded':False,'replication_existing':{'Is_Replica':False}}
    guards.append(('reject unseeded replica',source_assert,unseeded,False))
    state_assert=pick('roles/percona_server/tasks/configure.yml','Refuse stale topology or changed server identity')
    state={'percona_live':{'query_result':[[{'ro':0}]]},'percona_previous_state':{'content':base64.b64encode(json.dumps({'read_only':False,'server_id':101}).encode()).decode()},'percona_read_only':False,'percona_server_id':101}
    guards.append(('stable database identity',state_assert,state,True))
    drift=copy.deepcopy(state);drift['percona_live']['query_result'][0][0]['ro']=1
    guards.append(('reject topology drift',state_assert,drift,False))
    drift=copy.deepcopy(state);drift['percona_server_id']=102
    guards.append(('reject changed server ID',state_assert,drift,False))
    restore_assert=pick('roles/percona_backup/tasks/restore.yml','Require an explicit isolated restore target')
    guards.append(('reject unconfirmed restore',restore_assert,{'backup_restore_target':'another-host','backup_restore_id':'abc','backup_restore_workdir':'/tmp/restore'},False))
    recovery_assert=pick('roles/orchestrator/tasks/recovery.yml','Require deliberately tested fencing and routing before enabling recovery')
    guards.append(('reject untested recovery',recovery_assert,{'orchestrator_recovery_tested':False,'orchestrator_recovery_filters':[],'orchestrator_fencing_hook':'','orchestrator_routing_hook':''},False))
    copied_assert=pick('roles/percona_backup/tasks/restore.yml','Require stopped copied replication before clearing its metadata')
    guards.append(('copied channel is stopped',copied_assert,{'restored_channel':{'Replica_IO_Running':'No','Replica_SQL_Running':'No'}},True))
    guards.append(('reject running copied channel',copied_assert,{'restored_channel':{'Replica_IO_Running':'Yes','Replica_SQL_Running':'Yes'}},False))
    tasks=[{'name':'Define source address fixture','ansible.builtin.add_host':{'name':'db1','percona_address':'192.0.2.11'}}]
    for name, assertion, variables, success in guards:
        if success:
            tasks.append({'name':name,'ansible.builtin.assert':assertion,'vars':variables})
        else:
            # Run the actual guard; require failure, then continue the local fixture play.
            tasks.append({'name':name,'ansible.builtin.assert':assertion,'vars':variables,'register':'guard_result','ignore_errors':True})
            tasks.append({'name':'Check guard rejected unsafe input','ansible.builtin.assert':{'that':['guard_result is failed']}})
    path=temp/'guards.yml';path.write_text(yaml.safe_dump([{'hosts':'localhost','gather_facts':False,'tasks':tasks}],sort_keys=False))
    run(['ansible-playbook','-i','localhost,','-c','local',str(path)])
    print(f'Actual Ansible guard fixtures: {len(guards)} passed')


def check_module_parameters():
    modules = {}
    for path in ROOT.glob('roles/**/*.yml'):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, list):
            continue
        for task in data:
            for name, args in task.items():
                if name.startswith(('ansible.builtin.', 'community.')) and isinstance(args, dict) and name != 'ansible.builtin.set_fact':
                    modules.setdefault(name, []).append((path, args))
    result = run(['ansible-doc', '--json', *modules])
    docs = json.loads(result.stdout)
    for name, uses in modules.items():
        valid = set(docs[name]['doc'].get('options', {}))
        for path, args in uses:
            assert not set(args) - valid, f'{path}: unknown {name} arguments {set(args) - valid}'
    print(f'Module parameter schemas: {len(modules)} passed')


def check_links():
    count=0
    for path in [ROOT/'README.md', *ROOT.glob('docs/*.md'), *ROOT.glob('roles/*/README.md')]:
        text=re.sub(r'```.*?```','',path.read_text(),flags=re.S)
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            if '://' in link: continue
            name=link.split('#',1)[0]
            assert (path.parent/name).exists(), f'{path}: broken link {link}'
            count+=1
    print(f'Active documentation links: {count} passed')


if __name__=='__main__':main()
