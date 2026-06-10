import pandas as pd
import nltk

from nltk.stem import PorterStemmer
from nltk.tokenize import WordPunctTokenizer

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score



wordpunch = WordPunctTokenizer()
stemmer = PorterStemmer()

#data frame phaching 

data = pd.read_csv("./NLP/sms Spam/2sms_data.csv")


def stemm(text):
    text = text.lower()
    word = wordpunch.tokenize(text)


    stemming =[]
    for words in word:
        stemming_word = stemmer.stem(words)
        stemming.append(stemming_word)
    return " ".join(stemming)
    
data["new Message"] = data["message"].apply(stemm)

data["label"] = data["label"].map({
    "ham":0,
    "spam":1
})

X = data["new_message"]
y = data["label"]

cv = CountVectorizer()
X_vector = cv.fit_transform(X)