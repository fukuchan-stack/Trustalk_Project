import os
import asana
from asana.rest import ApiException

ASANA_ACCESS_TOKEN = os.getenv("ASANA_ACCESS_TOKEN")

if not ASANA_ACCESS_TOKEN:
    print("❌ エラー: 環境変数 `ASANA_ACCESS_TOKEN` が設定されていません。")
    exit()

print("Asanaに接続しています...")
configuration = asana.Configuration()
configuration.access_token = ASANA_ACCESS_TOKEN
api_client = asana.ApiClient(configuration)
print("✅ 接続に成功しました。")
print("-" * 30)

try:
    workspaces_api = asana.WorkspacesApi(api_client)
    projects_api = asana.ProjectsApi(api_client)

    workspaces_response = workspaces_api.get_workspaces({})
    for workspace in workspaces_response:
        # .name -> ['name'], .gid -> ['gid'] のように辞書としてアクセス
        print(f"🏢 ワークスペース名: {workspace['name']}")
        print(f"   🆔 ワークスペースGID: {workspace['gid']}\n")
        
        print("   プロジェクト一覧:")
        projects_response = projects_api.get_projects_for_workspace(workspace['gid'], opts={'limit': 100})
        
        project_found = False
        for project in projects_response:
            project_found = True
            # .name -> ['name'], .gid -> ['gid'] のように辞書としてアクセス
            print(f"     - 📜 プロジェクト名: {project['name']}")
            print(f"       🆔 プロジェクトGID: {project['gid']}")

        if not project_found:
            print("     - このワークスペースにプロジェクトはありません。")
            
        print("-" * 30)

except ApiException as e:
    print(f"❌ Asana API エラー: {e.body}")