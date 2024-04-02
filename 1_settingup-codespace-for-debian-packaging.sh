#!/bin/sh 

#Add debian and source repo
sudo tee /etc/apt/sources.list << EOF
deb http://deb.debian.org/debian/ bookworm main
#deb http://security.debian.org/debian-security/ bookworm-security main
deb-src http://deb.debian.org/debian/ bookworm main
deb http://ftp.us.debian.org/debian/ bookworm main
deb-src http://ftp.us.debian.org/debian/ bookworm main
#deb-src http://security.debian.org/debian-security/ bookworm-security main
#deb http://ftp.debian.org/debian stable-updates main
#deb http://archive.ubuntu.com/ubuntu bullseye-updates main
EOF

#Update package manager
sudo apt-get update

#Add GPG Keys
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 54404762BBB6E853
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys BDE6D2B9216EC7A8
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 0E98404D386FA1D9
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 6ED0E7B82643E131
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F8D2585B8783D481


#Update package manager
sudo apt-get update -y
#sudo apt-get upgrade -y
#sudo apt-get install debhelper dh-sequence-nodejs nodejs npm -y

#Install micro text editor and recommedation
sudo apt-get install --install-recommends --install-suggests micro
