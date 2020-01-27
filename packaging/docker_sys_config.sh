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

systemctl enable openvswitch.service
