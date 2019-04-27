# install packages via pip
pip install --upgrade pip
pip install -r requirements.txt

# natural language toolkit
python -m nltk.downloader wordnet
python -m nltk.downloader punkt
python -m nltk.downloader snowball_data
python -m nltk.downloader treebank
python -m nltk.downloader stopwords