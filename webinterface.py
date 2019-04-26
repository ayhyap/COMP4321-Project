import math
import pickle
import datetime as dt
from sqlitedict import SqliteDict
from flask import Flask, render_template, request
import datetime as dt
from query import tokenize_query
import numpy as np
from collections import defaultdict

app = Flask(__name__)

token2id = SqliteDict('phase2-token2id.sqlite', autocommit=True)
id2token = dict((v,k) for k,v in token2id.items())
page2id = SqliteDict('phase2-page2id.sqlite', autocommit=True)
id2page = dict((v,k) for k,v in page2id.items())
token_positionsDB = SqliteDict('phase2-token_positions.sqlite', autocommit=True)
metadataDB = SqliteDict('phase2-metadata.sqlite', autocommit=True)
linksDB = SqliteDict('phase2-links.sqlite', autocommit=True)
tokenid2page = SqliteDict('phase2-inverted_index.sqlite', autocommit=False)
page_title_token_positionsDB = SqliteDict('phase2-page_title_token_positions.sqlite', autocommit=True)
page_title_inverted_index = SqliteDict('phase2-page_title_inverted_index.sqlite', autocommit=False)


@app.route('/')
def startpage():
	return render_template('startpage.html')

@app.route('/result',methods = ['POST', 'GET'])
def result():
	if request.method == 'POST':
		result = request.form

		for key,value in result.items():
			query = value

		queryID, phraseQuery = tokenize_query(query, token2id)
		scores = defaultdict(int)
		searchResultsBody = searchEngine(queryID, tokenid2page)
		searchResultsPageTitle = searchEngine(queryID, page_title_inverted_index, title = True)
		searchResultsPhraseBody = searchEnginePhrase(phraseQuery, tokenid2page)
		searchResultsPhraseTitle = searchEnginePhrase(phraseQuery, page_title_inverted_index, title = True)
		for key in searchResultsBody.keys():
			scores[key] += searchResultsBody[key]
		for key in searchResultsPageTitle.keys():
			scores[key] += 7*searchResultsPageTitle[key]
		for key in searchResultsPhraseBody.keys():
			scores[key] += searchResultsPhraseBody[key]
		for key in searchResultsPhraseTitle.keys():
			scores[key] += 7*searchResultsPhraseTitle[key]

		for pageID, weight in scores.items():
			metadata = metadataDB[pageID]
			page_title, page_url, last_modified, page_size, keyword_count, maxfreqBody, maxfreqTitle = metadata
			scores[pageID] = weight / (int(keyword_count) * (len(queryID)+len(phraseQuery)))

		sortedSearchResults = sortDictionary(scores)

		pageScores = []
		pageTitles = []
		urls = []
		dates = []
		pageSizes = []
		keywordFreq = {}
		wordFreq = {}
		pageIDList = []
		parentLinks = []
		childLinks = []
		for page in sortedSearchResults:
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

			# TODO: Un-comment this when new linksDB is finished.
			tempListParent = []
			tempListChild = []
			pageLinksDict = linksDB[pageID]
			parentLinksIDs = pageLinksDict["in"]
			childLinksIDs = pageLinksDict["out"]
			
			for parentID in parentLinksIDs:
				tempListParent.append(id2page[parentID])
			for childID in childLinksIDs:
				tempListChild.append(id2page[childID])
			tempListChild = tempListChild[0:5]
			tempListParent = tempListParent[0:5]
			parentLinks.append(tempListParent)
			childLinks.append(tempListChild)

		return render_template("result.html", pageScores=pageScores, pageTitles = pageTitles, query = query, urls=urls, dates=dates, pageSizes=pageSizes, wordFreq=wordFreq, pageIDList=pageIDList, parentLinks=parentLinks, childLinks=childLinks)


def searchEngine(query, invertedIndexFile, title = False):
	TokenWeights = {}
	for queryToken in query:
		tokenDictionaryResult = {}
		if queryToken in invertedIndexFile:
			if queryToken != 0:
				tokenDictionaryResult = invertedIndexFile[queryToken]
				N = len(metadataDB) + 1
				df = len(tokenDictionaryResult)
				idf = math.log(N/df,2)
				for webPageID, positions in tokenDictionaryResult.items():
					# maxTermFreq = float(metadataDB[webPageID][6 if title else 5])
					maxTermFreq = float(np.sqrt(len(page_title_token_positionsDB[webPageID])+1) if title else metadataDB[webPageID][5])
					frequency = len(positions)
					weight = (frequency * idf)/maxTermFreq
					if webPageID in TokenWeights:
						TokenWeights[webPageID] += weight
					else:
						TokenWeights[webPageID] = weight

	return TokenWeights


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
    # app.run()
