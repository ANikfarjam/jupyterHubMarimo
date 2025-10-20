### Test result

To test your server run
```bach
    just test-api <username> <document name with .py>
```

![Test](./screenshots/test.png)

### Architecture Diagram

![Architecture Diagram](./screenshots/Design%20Diagram.jpg)

### User Creation Flow
![User Creation Flow](./screenshots/usercreationflow.png)

### Notebook Flow
![NotebookFlow](./screenshots/NotebookFlow.png)

# JupyterHub with Marimo Notebooks

This repository provides a complete configuration to deploy a JupyterHub server with Marimo notebook support.

## Prerequisites

### Package Installation

```bash
# JupyterHub and components
pip install jupyterhub notebook jupyterlab

# Just command runner  
pip install just

# Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

## Buld Server

```bash
just config
```

### Clean up ports

```bash
just clean-ports
```
