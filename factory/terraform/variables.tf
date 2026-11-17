variable "admin_cidr" {
  description = "CIDR allowed to reach SSH, for example 203.0.113.7/32"
  type        = string
}

variable "ssh_public_key" {
  description = "Public key installed for root on the VM"
  type        = string
}

variable "server_type" {
  type    = string
  default = "cx23"
}

variable "location" {
  type    = string
  default = "nbg1"
}

variable "k3s_version" {
  type    = string
  default = "v1.37.2+k3s1"
}
