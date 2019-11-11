install -o root -g root -d /etc/sysconfig/network-scripts

cat > /etc/NetworkManager/conf.d/97-trace-logging.conf <<EOF
[logging]
level=TRACE
domains=ALL
EOF

sed -i \
    -e 's/^#RateLimitInterval=.*/RateLimitInterval=0/' \
    -e 's/^#RateLimitBurst=.*/RateLimitBurst=0/' \
    /etc/systemd/journald.conf

cat > /etc/NetworkManager/conf.d/97-no-auto-default.conf <<EOF
# Workaround for https://bugzilla.redhat.com/1687937
[main]
no-auto-default=*
EOF

cat > /etc/NetworkManager/conf.d/97-use-dhclient.conf <<EOF
# Workaround for https://bugzilla.redhat.com/show_bug.cgi?id=1749358
[main]
dhcp=dhclient
EOF

systemctl enable openvswitch.service
