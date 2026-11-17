locals {
  name          = "software-factory"
  anywhere      = ["0.0.0.0/0", "::/0"]
  public_ports  = { http = "80", kube_api = "6443" }
  ssh_port      = "22"
  manifests_dir = "/var/lib/rancher/k3s/server/manifests"
}

resource "hcloud_ssh_key" "admin" {
  name       = local.name
  public_key = var.ssh_public_key
}

resource "hcloud_primary_ip" "this" {
  name        = local.name
  type        = "ipv4"
  location    = var.location
  auto_delete = false
}

resource "hcloud_firewall" "this" {
  name = local.name

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = local.ssh_port
    source_ips = [var.admin_cidr]
  }

  dynamic "rule" {
    for_each = local.public_ports
    content {
      direction  = "in"
      protocol   = "tcp"
      port       = rule.value
      source_ips = local.anywhere
    }
  }
}

resource "hcloud_server" "this" {
  name         = local.name
  server_type  = var.server_type
  image        = "ubuntu-24.04"
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.admin.id]
  firewall_ids = [hcloud_firewall.this.id]

  public_net {
    ipv4         = hcloud_primary_ip.this.id
    ipv6_enabled = false
  }

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    k3s_version       = var.k3s_version
    ipv4              = hcloud_primary_ip.this.ip_address
    manifests_dir     = local.manifests_dir
    deployer_manifest = filebase64("${path.module}/../cluster/deployer.yaml")
  })
}
