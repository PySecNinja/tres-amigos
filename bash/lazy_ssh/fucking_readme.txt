# Example SSH config file
# Save as ~/.ssh/config and ensure permissions are set to 600

Host dev
    HostName your.dev.hostname.com
    User your-username
    IdentityFile ~/.ssh/dev_key.pem

Host test
    HostName your.test.hostname.com
    User your-username
    IdentityFile ~/.ssh/test_key.pem

Host prod
    HostName your.prod.hostname.com
    User your-username
    IdentityFile ~/.ssh/prod_key.pem

# Optional: Apply global options to all hosts
Host *
    ForwardAgent yes
    AddKeysToAgent yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
