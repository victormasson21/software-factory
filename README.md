# Software factory

An issue goes in, a deployed change comes out. The design is in [docs/planning.md](docs/planning.md).

## Start and stop the infrastructure

`make up` creates one Hetzner VM with k3s, gives GitHub the deploy credential, and starts one deploy. `make down` destroys the VM.

Prerequisites: `terraform`, `gh`, `ssh`, and a Hetzner Cloud API token.

Set these variables in the shell before you run either target:

| Variable                | Value                                                    |
| ----------------------- | -------------------------------------------------------- |
| `HCLOUD_TOKEN`          | Hetzner Cloud API token                                  |
| `GH_TOKEN`              | GitHub token for the account that owns the repo          |
| `TF_VAR_admin_cidr`     | Your public IP as a CIDR, for example `203.0.113.7/32`   |
| `TF_VAR_ssh_public_key` | The public key that `ssh` uses by default                |

```sh
make up
make down
```
