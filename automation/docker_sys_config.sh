install -o root -g root -d /etc/sysconfig/network-scripts
echo -e "[logging]\nlevel=TRACE\ndomains=ALL\n" > \
    /etc/NetworkManager/conf.d/97-docker-build.conf
echo -e "[device]\nmatch-device=*\nmanaged=0\n" >> \
    /etc/NetworkManager/conf.d/97-docker-build.conf
echo -e "[main]\nno-auto-default=*\n" >> \
    /etc/NetworkManager/conf.d/97-docker-build.conf
sed -i 's/#RateLimitInterval=30s/RateLimitInterval=0/' \
    /etc/systemd/journald.conf
sed -i 's/#RateLimitBurst=1000/RateLimitBurst=0/' \
    /etc/systemd/journald.conf
systemctl enable openvswitch.service
