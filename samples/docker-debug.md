# Docker Container Debugging

## Container won't start

1. Check logs: `docker logs <container>`
2. Inspect exit code: `docker ps -a` — 0 means clean exit, non-zero is an app error.
3. Check config: `docker inspect <container>`

## Container starts then dies

- Usually the main process exits. Run interactively to see output:
  `docker run -it --rm <image> /bin/sh`
- Check OOM kills: `docker inspect <container> | grep -i oom`

## Networking issues

- List networks: `docker network ls`
- Test connectivity between containers: `docker exec <c1> ping <c2>`
- Check published ports: `docker port <container>`

## Cleanup

- Stopped containers: `docker container prune`
- Unused images: `docker image prune`
