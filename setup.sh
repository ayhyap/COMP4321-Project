# install python 3.6
sudo yum -y update
sudo yum -y install https://centos7.iuscommunity.org/ius-release.rpm
sudo yum -y install python36u 
sudo yum -y install python36u-pip

# check python works
python3.6 -V
pip3.6 -V

# install packages via pip
sudo pip3.6 install --upgrade pip
sudo pip3.6 install numpy

# key-value database
sudo pip3.6 install sqlitedict

# natural language toolkit
sudo pip3.6 install nltk
python3.6 -m nltk.downloader wordnet
python3.6 -m nltk.downloader punkt
python3.6 -m nltk.downloader snowball_data
python3.6 -m nltk.downloader treebank
python3.6 -m nltk.downloader stopwords

# html parser
sudo pip3.6 install beautifulsoup4

# other stuff
sudo pip3.6 install python-dateutil

sudo pip3.6 install flask

sudo pip3.6 install gunicorn