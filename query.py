import re
from collections import defaultdict
from nltk.tokenize import word_tokenize
from nltk.stem import snowball, wordnet
from nltk.corpus import stopwords

stopwords = stopwords.words('english')
snowball = snowball.EnglishStemmer()
wordnet = wordnet.WordNetLemmatizer()
_ = wordnet.lemmatize('hi')
# input:    query string
#           token2id dictionary (or sqlitedb object)
# output:   list of ints    tokenIDs
#           list of list of ints    phrases of tokenIDs
#                   e.g.[[2,19], [18,20], [12,44,36]]
def tokenize_query(query, token2id):
    phrases = re.findall('\"(.+?)\"', query)
    # list of strings inside quotation marks
    query = re.sub('\"(.+?)\"', '', query)
    # remaining query string without quotes

    query_tokens = word_tokenize(query)
    query_tokens = [token for token in query_tokens if token.lower() not in stopwords]

    for i in range(len(query_tokens)-1,-1,-1):
        if not re.fullmatch('[a-zA-Z0-9\-/]+', query_tokens[i]) or re.fullmatch('[\-/]+', query_tokens[i]):
            # do not match unk tokens
            del query_tokens[i]
        elif len(query_tokens[i]) <= 1:
            del query_tokens[i]
    query_tokens = [wordnet.lemmatize(token) for token in query_tokens]
    query_tokens = [snowball.stem(token) for token in query_tokens]

    query_ids = []
    for token in query_tokens:
        try:
            query_ids.append(token2id[token])
        except KeyError:
            continue

    # handle phrases
    all_phrase_ids = []
    for phrase in phrases:
        # phrase is a string of words
        phrase_tokens = word_tokenize(phrase)
        phrase_tokens = [token for token in phrase_tokens if token.lower() not in stopwords]
        for i in range(len(phrase_tokens)-1,-1,-1):
            if not re.fullmatch('[a-zA-Z0-9\-/]+', phrase_tokens[i]) or re.fullmatch('[\-/]+', phrase_tokens[i]):
                phrase_tokens[i] = '<unk>'
            elif len(phrase_tokens[i]) <= 1:
                del phrase_tokens[i]
        phrase_tokens = [wordnet.lemmatize(token) for token in phrase_tokens]
        phrase_tokens = [snowball.stem(token) for token in phrase_tokens]

        phrase_ids = []
        for token in phrase_tokens:
            try:
                phrase_ids.append(token2id[token])
            except KeyError:
                phrase_ids.append(token2id['<unk>'])

        if len(phrase_ids) > 1:
            all_phrase_ids.append(phrase_ids)
        else:
            if len(phrase_ids) == 0:
                continue
            elif phrase_ids[0] == token2id['<unk>']:
                continue
            else:
                query_ids.append(phrase_ids[0])
    
    return query_ids, all_phrase_ids

if __name__ == '__main__':
    from sqlitedict import SqliteDict
    token2id = SqliteDict('phase2-token2id.sqlite', autocommit=True)
    tokenize_query('"Hong Kong" and "New York"', token2id)
