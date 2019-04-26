import math
import pickle
import datetime as dt
import datetime as dt
import numpy as np
import heapq
from sqlitedict import SqliteDict
from flask import Flask, render_template, request
from query import tokenize_query
from collections import defaultdict
from time import process_time
from numba import jit
from copy import deepcopy

ham_sandwich = True
app = Flask(__name__)

token2id = SqliteDict('phase2-token2id.sqlite', journal_mode='OFF')
page2id = SqliteDict('phase2-page2id.sqlite', journal_mode='OFF')
metadataDB = SqliteDict('phase2-metadata.sqlite', journal_mode='OFF')
linksDB = SqliteDict('phase2-links.sqlite', journal_mode='OFF')
invertedIndex = SqliteDict('phase2-inverted_index.sqlite', journal_mode='OFF')
token_positionsDB = SqliteDict('phase2-token_positions.sqlite', journal_mode='OFF')
page_title_token_positionsDB = SqliteDict('phase2-page_title_token_positions.sqlite', journal_mode='OFF')
page_title_inverted_index = SqliteDict('phase2-page_title_inverted_index.sqlite', journal_mode='OFF')

if ham_sandwich:
    # token2id = dict((v,int(k)) for v,k in token2id.items())
    # page2id = dict((v,int(k)) for v,k in page2id.items())
    metadataDB = dict((int(v),k) for v,k in metadataDB.items())
    linksDB = dict((int(v),k) for v,k in linksDB.items())
    invertedIndex = dict((int(v),k) for v,k in invertedIndex.items())
    token_positionsDB = dict((int(v),k) for v,k in token_positionsDB.items())
    page_title_token_positionsDB = dict((int(v),k) for v,k in page_title_token_positionsDB.items())
    page_title_inverted_index = dict((int(v),k) for v,k in page_title_inverted_index.items())

id2token = dict((v,k) for k,v in token2id.items())
id2page = dict((v,k) for k,v in page2id.items())

@app.route('/')
def startpage():
    return render_template('startpage.html')

@app.route('/result',methods = ['POST', 'GET'])
def result():
    if request.method == 'POST':
        result = request.form
        
        for key,value in result.items():
            query = value
        
        start = process_time()
        queryTokens, queryPhrases = tokenize_query(query, token2id)
        print(process_time()-start, '\tTokenize')
        
        scores = defaultdict(int)
        
        start = process_time()
        searchResultsBody = searchEngine(queryTokens, invertedIndex)
        print(process_time()-start, '\tSE-Body')
        
        start = process_time()
        searchResultsPageTitle = searchEngine(queryTokens, page_title_inverted_index, title = True)
        print(process_time()-start, '\tSE-Title')
        
        start = process_time()
        searchResultsPhraseBody = searchEnginePhrase(queryPhrases, invertedIndex)
        print(process_time()-start, '\tSE-BodyPhrase')
        
        start = process_time()
        searchResultsPhraseTitle = searchEnginePhrase(queryPhrases, page_title_inverted_index, title = True)
        print(process_time()-start, '\tSE-TitlePhrase')
        
        for key in searchResultsBody.keys():
            scores[key] += searchResultsBody[key]
        for key in searchResultsPageTitle.keys():
            scores[key] += 7*searchResultsPageTitle[key]
        for key in searchResultsPhraseBody.keys():
            scores[key] += searchResultsPhraseBody[key]
        for key in searchResultsPhraseTitle.keys():
            scores[key] += 7*searchResultsPhraseTitle[key]
        
        for pageID, weight in scores.items():
            scores[pageID] = weight / (int(metadataDB[pageID][4]) * (len(queryTokens)+len(queryPhrases)))
        
        start = process_time()
        sortedSearchResults = sortDictionary(scores)
        print(process_time()-start, '\tSort Scores')
        
        
        start = process_time()
        
        pageScores = []
        pageTitles = []
        urls = []
        dates = []
        pageSizes = []
        wordFreq = {}
        pageIDList = []
        parentLinks = []
        childLinks = []
        for page in sortedSearchResults[:50]:
            pageID = page[0]
            pageIDList.append(pageID)
            pageScore = page[1]
            pageScores.append(pageScore)
            page_title, page_url, last_modified, page_size, keyword_count, maxfreqBody, maxfreqTitle = metadataDB[pageID]
            if page_title == "":
                page_title = "((No Page Title))"
            pageTitles.append(page_title)
            urls.append(page_url)
            last_modified = dt.datetime.now(tz= dt.timezone.utc).fromtimestamp(float(last_modified))
            dates.append(last_modified)
            
            suffix = ' b'
            page_size = int(page_size)
            if page_size > 1024:
                page_size /= 1024
                suffix = ' kb'
            if page_size > 1024:
                page_size /= 1024
                suffix = ' mb'
            pageSizes.append(str(int(page_size))+suffix)
            
            
            
            pageTokenPositions = token_positionsDB[pageID]
            tempDict = {}
            for token, positions in pageTokenPositions.items():
                if token != 0:
                    word = id2token[int(token)]
                    freq = len(positions)
                    tempDict[word] = freq
            tempDict = sortDictionary(tempDict)
            tempDict = tempDict[0:5]
            wordFreq[pageID] = tempDict
            

            pageLinksDict = linksDB[pageID]
            tempListParent = [id2page[parentID] for parentID in pageLinksDict['in'][:5]]
            tempListChild = [id2page[childID] for childID in pageLinksDict['out'][:5]]
            parentLinks.append(tempListParent)
            childLinks.append(tempListChild)
        print(process_time()-start, '\tCompileResultsData')
        return render_template("result.html", pageScores=pageScores, pageTitles = pageTitles, query = query, urls=urls, dates=dates, pageSizes=pageSizes, wordFreq=wordFreq, pageIDList=pageIDList, parentLinks=parentLinks, childLinks=childLinks)

# @jit(nopython = False)
def searchEngine(query, invertedIndexFile, title = False):
    scores = defaultdict(float)
    N = len(metadataDB) + 1
    for token in query:
        if token == 0:
            continue
        
        start = process_time()
        try:
            page2positions = invertedIndexFile[token]
        except:
            continue
        
        print(process_time()-start, '\t\tAccessInvertedIndex')
        # df = len(page2positions)
        idf = math.log(N/len(page2positions),2)
        
        start = process_time()
        for webPageID, positions in page2positions.items():
            ## maxTermFreq = float(metadataDB[webPageID][6 if title else 5])
            
            # experimental
            # maxTermFreq = float(np.sqrt(len(page_title_token_positionsDB[webPageID])+1) if title else metadataDB[webPageID][5])
            # frequency = len(positions)
            # weight = (len(positions) * idf) / float(np.sqrt(len(page_title_token_positionsDB[webPageID])+1) if title else metadataDB[webPageID][5])
            scores[webPageID] += (len(positions) * idf) / (1 if title else int(metadataDB[webPageID][5]))
        print(process_time()-start, '\t\tCalculateScores')
    return scores

# @jit(nopython=False)
def searchEnginePhrase(queryPhrases, invertedIndexFile, title = False):
    scores = defaultdict(int)
    for phrase in queryPhrases:
        tempList = []
        for tokenID in phrase:
            tempList.append(list(invertedIndexFile[tokenID].keys()))
        candidates = tempList[0]
        for i in range(1,len(tempList)):
            candidates = np.intersect1d(candidates, tempList[i], True).tolist()
        pagePhraseFrequency = {}
        for pageID in candidates:
            phraseFrequency = 0
            for startingPosition in invertedIndexFile[phrase[0]][pageID]:
                fullmatch = False
                for i in range(1, len(phrase)):
                    match = False
                    for tokenPosition in invertedIndexFile[phrase[i]][pageID]:
                        if tokenPosition == startingPosition + i:
                            match = True
                            break
                        elif tokenPosition > startingPosition + 1:
                            break
                    if not match:
                        break
                if match:
                    phraseFrequency += 1

            maxTermFreq = float(np.sqrt(len(page_title_token_positionsDB[pageID])+1) if title else metadataDB[pageID][5])
            pagePhraseFrequency[pageID] = phraseFrequency/maxTermFreq 
        df = 0
        for frequency in pagePhraseFrequency.values():
            if frequency > 0:
                df += 1
        N = len(metadataDB) + 1
        idf = math.log(N/df, 2)
        for key in pagePhraseFrequency.keys():
            pagePhraseFrequency[key] *= idf
            scores[key] += pagePhraseFrequency[key]
    return scores


def sortDictionary(TokenWeights):
    TokenWeightsTuple = [(k, v) for k, v in TokenWeights.items()]
    TokenWeightsTupleSorted = sorted(TokenWeightsTuple, key=lambda x: x[1], reverse=True)
    #TokenWeightsTupleSorted = TokenWeightsTupleSorted[0:50]

    return TokenWeightsTupleSorted


if __name__ == '__main__':
    pass
    # app.run(host="0.0.0.0", port="5000", debug = True)
    app.run()
