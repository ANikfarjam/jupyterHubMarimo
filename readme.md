### JupytherHub and Mrimo
This reposetory include instruction for setting up a jupyterhub server with a marimo proxy. 

### Install the following packages

```
pip install jupyterhub notebook jupyterlab
#istall just
pip install just
#docker compose
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

Installing just run:
```
# to create the jhub docker image
just config

#to clear ports process
just clean-ports

