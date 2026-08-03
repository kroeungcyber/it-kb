# Nginx Restart Runbook

## When to restart vs reload

Use `reload` for config changes (zero downtime). Use `restart` only when
reload fails or a binary/module change requires it.

## Standard procedure

1. Validate config first: `sudo nginx -t`
2. Reload gracefully: `sudo systemctl reload nginx`
3. If reload fails, check the error: `journalctl -u nginx -n 50`
4. Full restart as last resort: `sudo systemctl restart nginx`

## Common pitfalls

- Skipping `nginx -t` and taking the site down with a syntax error.
- Port conflicts: check with `ss -tlnp | grep nginx`.
- Stale PID file after an unclean stop: remove `/run/nginx.pid` and retry.

## Verification

- `curl -I http://localhost` returns 200.
- `systemctl status nginx` shows active (running).
