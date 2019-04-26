# (tested on a new VM)
# To setup, put the project files in a folder, the run the command (with sudo rights):
bash setup.sh

# If you aren't using centos7, you will have to read the setup.sh and do the equivalent commands for your OS.

# After setup, run the crawler. It is currently set to only crawl 30 pages. 
# Remove the limit in crawl.py to crawl over all cse.ust.hk websites.
# Note that the full crawling process will take a few hours if no limit is set.
python3.6 crawler.py


# To run the search engine on localhost, run:
python3.6 webinterface.py

# It will then be accessible on the same computer via localhost on port 5000 (i think) (127.0.0.1:5000)


# Because we couldn't figure out how to allow other devices to access the server, we hosted our search engine on Heroku
# It is accessible at: https://infinite-reef-85666.herokuapp.com

# ============
#
# Our system uses several key-value tables:
#
# PAGE-RELATED
#   metadata
#   key: int pageID
#   value: array of 6 values...
#               str                 page_title      (page title)
#               str                 page_url        (page url)
#               str(float)          last_modified   (last modified unix timestamp)
#               str(see below)      page_size       (plaintext page size in bytes prior to preprocessing)
#               str(int)            keyword_count   (total number of keywords)
#               str(int)            token_tfmax     (frequency of most frequent token in page)
#   (all the values are stored as strings due to storage limitations)
#   (they need to be casted back into their original format for normal use)
#   (to cast the timestamp, use:
#       import datetime
#       last_modified = datetime.datetime.now(tz= dt.timezone.utc).fromtimestamp(last_modified)
#    then to get a nice date-time string, use: last_modified.ctime()
#   )
#
#   token_positions
#   key:    pageID  int
#   value:  python (default) dictionary of...
#               key:    int                 tokenID
#               value:  list of ints        positions of occurrences of token in page
#   (tokens are processed using WordNet lemmatizer, Snowball stemmer and stopword removal from python NLTK module)
#   (tokens include image alt text)
#
#
#   page_title_token_positions
#   key:    pageID  int
#   value:  python (default) dictionary of...
#               key:    int                 tokenID
#               value:  list of ints        positions of occurrences of token in page title
#   (all preprocessing is the same as token_positions)
#
#
#   links
#   key:    int    pageID
#   value:  python dictionary of...
#               key:            str                 'in' or 'out' (for incoming and outgoing links)
#               value('in'):    list of ints        pageIDs of incoming linked websites
#               value('out'):   list of ints        pageIDs of outgoing linked websites
#
#
# ID-MAPPINGS
#   token2id
#   key:    str     token
#   value:  int     tokenID
#   (id's can be mapped back to tokens by swapping keys/values in python)
#   (NOTE: id 0 is reserved for <unk>, an unknown token which is used for approximate phrase matching with punctuation)
#   (       <unk> should NOT be used in the vector space model)
#
#
#   page2id
#   key:    str     page url
#   value:  int     pageID
#   (id's can be mapped back to pages by swapping keys/values in python)
#
#
# INVERTED INDEX
#   inverted_index
#   key:    int     tokenID
#   value:  python dictionary of...
#               key:    int             pageID
#               vaue:   list of ints    positions of occurrences of token in page
#   (inverted index is not used in phase 1)
#
#
#   page_title_inverted_index
#   key:    int     tokenID
#   value:  python dictionary of...
#               key:    int             pageID
#               vaue:   list of ints    positions of occurrences of token in page title
#   (same as inverted_index, but for page title)
#
# ===================
#
# We used Python dictionaries to store token counts and outgoing links because 
# they access elements using a hash function on the key, 
# which allows for average-case constant time element access, better than the log(n) of sorted binary trees.
#
# The python module we used for the database (sqlitedict) has limitations on the 
# complexity of the value objects which prevents it from storing large or multi-type Python dictionaries.