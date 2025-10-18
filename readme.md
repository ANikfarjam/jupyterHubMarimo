
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

