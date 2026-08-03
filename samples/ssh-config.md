# SSH Configuration Runbook

## Client config (~/.ssh/config)

```
Host prod
    HostName 203.0.113.10
    User deploy
    IdentityFile ~/.ssh/id_ed25519
    Port 22
```

## Hardening checklist (/etc/ssh/sshd_config)

- `PermitRootLogin no`
- `PasswordAuthentication no` (keys only)
- `MaxAuthTries 3`
- After edits: `sudo sshd -t` then `sudo systemctl reload sshd`

## Troubleshooting

- Verbose client output: `ssh -vvv user@host`
- Permission denied (publickey): check `~/.ssh` is 700, key files 600.
- Agent not forwarding keys: `ssh-add -l` then `ssh -A user@host`.
