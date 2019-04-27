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
sudo pip3.6 install -r requirements.txt

# natural language toolkit
python3.6 -m nltk.downloader wordnet
python3.6 -m nltk.downloader punkt
python3.6 -m nltk.downloader snowball_data
python3.6 -m nltk.downloader treebank
python3.6 -m nltk.downloader stopwords