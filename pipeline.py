# -*- coding: utf-8 -*-
"""Pipeline.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1iZ9FGevhqTBm6E1De8bWnFdmiXCkYQo-

### Library
"""

#from google.colab import drive
#drive.mount('/content/drive')

# Import library
import pandas as pd
import numpy as np
from tqdm import tqdm
import networkx as nx
import random
import datetime
import tensorflow as tf
import matplotlib.pyplot as plt

import itertools
import re

import warnings
warnings.filterwarnings("ignore")

import tensorflow as tf
import tensorflow.keras as keras

import time

import os

"""# Load dataset"""

def load_project(path, project_name):
  df = pd.read_csv(path + 'attribute.csv')
  graph = pd.read_csv(path + 'graph.csv', delimiter=',')
  df = df.fillna('')
  return df, graph

"""# Preprocessing"""

# ---- from nltk.stem import LancasterStemmer
import nltk
nltk.download('wordnet')

# from nltk.stem import LancasterStemmer
from nltk.stem import WordNetLemmatizer

# wordnet_lemmatizer = WordNetLemmatizer()
lancaster = nltk.stem.LancasterStemmer()

from nltk.corpus import stopwords
nltk.download('stopwords')

# Init stop_words list
stop_words = set(stopwords.words('english')) 
stop_words.add('e.g')
stop_words.add('i.e')
stop_words.add('https')
stop_words.add('http')
stop_words.add('org')
stop_words.add('www')
stop_words.add('href')
stop_words.remove('all')

def stemmer_sentence(sentence):
    result = []
    for word in sentence.split(" "):
        # result.append(wordnet_lemmatizer.lemmatize(word))
        result.append(lancaster.stem(word))
    return " ".join(result)

def remove_html(text):
  from bs4 import BeautifulSoup
  text = BeautifulSoup(text).get_text().replace('\n',' ').replace('\t',' ')
  return text

def delete_number(text):
  text = text.split()
  text = [text[i] for i in range(len(text)) if re.search("\d", text[i])==None]
  text = " ".join(text)
  return text

def get_links(text):
  text = re.findall(r'(https?://\S+)', text)
  text = " ".join(text)
  text = text.replace('"','')
  text = text.replace(')','')
  text = text.replace('(','')
  text = text.replace("'",'')
  text = text.replace(">",'')
  text = text.replace("<",'')
  text = text.replace(",",'')
  text = text.replace("a",'')
  return text

def remove_link(text):
  links = re.findall(r'(https?://\S+)', text)
  links = '|'.join(links)
  text = text.replace(links,'')
  return text

def preprocessing(df):
  # Choose necessary features
  columns = ["title", "description", "summary", "key", "created", "updated"]
  processing_df = df.loc[:, columns]

  # Lowercase all texts
  processing_df["title"] = processing_df["title"].str.lower()
  processing_df["description"] = processing_df["description"].str.lower()
  processing_df["summary"] = processing_df["summary"].str.lower()
  processing_df["key"] = processing_df["key"].str.lower()

  # Get http links
  processing_df["http_links"] = processing_df["description"].apply(get_links)
  processing_df["description"] = processing_df["description"].apply(remove_link)

  # Remove all number
  processing_df["title"] = processing_df["title"].apply(delete_number)
  processing_df["description"] = processing_df["description"].apply(delete_number)
  processing_df["summary"] = processing_df["summary"].apply(delete_number)

  # Remove html special elements
  processing_df["http_links"] = processing_df["http_links"].apply(remove_html)

  # Remove stopwords
  pat = r'\b(?:{})\b'.format('|'.join(stop_words))
  processing_df["title"] = processing_df["title"].str.replace(pat, '')
  processing_df["description"] = processing_df["description"].str.replace(pat, '')
  processing_df["summary"] = processing_df["summary"].str.replace(pat, '')

  # Remove punctuation and space
  processing_df["title"] = processing_df["title"].str.replace("[^\w]", " ", regex=True).str.replace("[ ]+", " ", regex=True).str.strip()
  processing_df["description"] = processing_df["description"].str.replace("[^\w]", " ", regex=True).str.replace("[ ]+", " ", regex=True).str.strip()
  processing_df["summary"] = processing_df["summary"].str.replace("[^\w]", " ", regex=True).str.replace("[ ]+", " ", regex=True).str.strip()

  # Stemming
  processing_df["title"] = processing_df["title"].apply(stemmer_sentence)
  processing_df["description"] = processing_df["description"].apply(stemmer_sentence)
  processing_df["summary"] = processing_df["summary"].apply(stemmer_sentence)

  return processing_df

"""### Encoding graph"""

def change_graph(row):
  new_row = []
  for i in row:
    if i==0:
      new_row.append([1,0])
    else:
      new_row.append([0,1])
  return new_row

"""# Model

### Get features
"""

def get_string_feature(df, choose_feature_string):
  df["title"] = df["title"].str.replace("[ ]+", " ", regex=True).str.strip()
  df["description"] = df["description"].str.replace("[ ]+", " ", regex=True).str.strip()
  df["summary"] = df["summary"].str.replace("[ ]+", " ", regex=True).str.strip()

  # Extract data from dataframe
  title = df['title'].values
  description = df['description'].values
  summary = df['summary'].values

  if len(choose_feature_string)==1:
    feature = df[choose_feature_string[0]].values
    all_text = [feature[i] for i in range(len(df)) ]
  else:
    for index in range(0, len(choose_feature_string)):
      feature = df[choose_feature_string[index]].values
      if index==0:
        all_text = feature
      else:
        all_text = [all_text[i] + ' ' + feature[i] for i in range(0, len(all_text))]

  return all_text

def get_time_features(df):
  createds = pd.to_datetime(df['created'])
  updateds = pd.to_datetime(df['updated'])
  return [createds, updateds]

"""### Tokenize and padding
title, des, summary
"""

from keras.preprocessing.sequence import pad_sequences
def tokenize_padding_text(value_maxlen, tokenizer, text):
  # Tokenize and padding input
  tokenized_X = tokenizer.texts_to_sequences(text)
  padded_X = pad_sequences(tokenized_X, maxlen=value_maxlen, truncating="post")

  return padded_X

"""### Split data"""

def split_data(createds, graph, time_split):
  # Get date to split data
  x = createds[0]
  check_date = x + abs(datetime.timedelta(time_split))

  train_nodes = []
  test_nodes = []

  for i in range(0, len(createds)):
    if createds[i]<=check_date:
      train_nodes.append(i)
    else:
      test_nodes.append(i) 

  # Delete all lonely nodes in test
  c = 0
  new_test_node = []
  for i in test_nodes:
    t = True
    for j in graph[i,:]:
      if j[1]!=0: # has linked
        t = False
    if not t:
      c+=1
      new_test_node.append(i)

  test_nodes = new_test_node
  all_nodes = train_nodes + test_nodes

  return train_nodes, test_nodes, all_nodes

"""## Training

### Pairing training
"""

def get_train_pairs(graph, list_nodes):
  # list_nodes: list of nodes in input

  # Get size
  size = len(list_nodes)

  # Get index of pairs
  pairs = np.empty((size*(size-1)//2,2))
  # Get label
  labels = np.empty((size*(size-1)//2,2))

  c=0
  for i in tqdm(range(0, size-1)):
    for j in range(i+1, size):
      u = list_nodes[i]
      v = list_nodes[j]
      # Get index of pairs
      pairs[c] = [u,v]
      # Get label
      labels[c] = graph[u][v]
      c+=1

  pairs = pairs[:c]
  labels = labels[:c]
  return pairs, labels

def get_pairs(graph, list_nodes_1, list_nodes_2):
  # list_nodes_1: list of nodes in input
  # list_nodes_2: list of nodes in dataset

  # Get size
  size_1 = len(list_nodes_1)
  size_2 = len(list_nodes_2)

  # Get index of pairs
  pairs = np.empty((size_1*size_2,2))
  # Get label
  labels = np.empty((size_1*size_2,2))

  c=0
  for i in tqdm(range(0, size_1)):
    for j in range(0, size_2):
      u = list_nodes_1[i]
      v = list_nodes_2[j]
      if u!=v:
        # Get index of pairs
        pairs[c] = [u,v]
        # Get label
        labels[c] = graph[u][v]
        c+=1

  pairs = pairs[:c]
  labels = labels[:c]
  return pairs, labels

"""### Get training dataset"""

def create_pair_dataset(pair, label):
  # Get data
  # Index of pairs which have link
  link_data_index = np.array([i for i in range(len(pair)) if label[i][0]==0])

  # Index of pairs which don't have link
  non_link_data_index = np.array([i for i in range(len(pair)) if label[i][0]==1])

  return link_data_index, non_link_data_index

def get_separated_data_pairs(input, add_feature):
  pair, label, createds, updateds, texts = input

  link_data_index, non_link_data_index = create_pair_dataset(pair, label)
  
  link_data = []
  non_link_data = []

  # Get link_data
  for index in tqdm(link_data_index):
      p = pair[index]
      u = int(p[0])
      v = int(p[1])
      link_input_A = texts[u]
      link_input_B = texts[v]
      link_data.append([link_input_A, link_input_B])
      
  # Get non_link_data
  for index in tqdm(non_link_data_index):
      p = pair[index]
      u = int(p[0])
      v = int(p[1])
      non_link_input_A = texts[u]
      non_link_input_B = texts[v]
      non_link_data.append([non_link_input_A, non_link_input_B])
  
  if add_feature != None:
    link_other_features = []
    non_link_other_features = []
    
    # Get link_data
    for index in tqdm(link_data_index):
        p = pair[index]
        u = int(p[0])
        v = int(p[1])

        cre_u = createds[u]
        
        if add_feature==1:
          cre_v = createds[v]
          cre_cre = abs((cre_u - cre_v).days)
          link_other_features.append([cre_cre])
        else:
          if add_feature==2:
            update_v = updateds[v]
            cre_up = abs((cre_u - update_v).days)
            link_other_features.append([cre_up])
          else:
            cre_v = createds[v]
            cre_cre = abs((cre_u - cre_v).days)
            update_v = updateds[v]
            cre_up = abs((cre_u - update_v).days)
            link_other_features.append([cre_cre, cre_up])


    # Get non_link_data
    for index in tqdm(non_link_data_index):
        p = pair[index]
        u = int(p[0])
        v = int(p[1])
        
        cre_u = createds[u]
        
        if add_feature==1:
          cre_v = createds[v]
          cre_cre = abs((cre_u - cre_v).days)
          non_link_other_features.append([cre_cre])
        else:
          if add_feature==2:
            update_v = updateds[v]
            cre_up = abs((cre_u - update_v).days)
            non_link_other_features.append([cre_up])
          else:
            cre_v = createds[v]
            cre_cre = abs((cre_u - cre_v).days)
            update_v = updateds[v]
            cre_up = abs((cre_u - update_v).days)
            non_link_other_features.append([cre_cre, cre_up])

    return link_data, non_link_data, link_other_features, non_link_other_features
    
  return link_data, non_link_data

"""## Training Model"""

def generate_input(input_init, add_feature, link_data, non_link_data, link_other_features = None, non_link_other_features = None ,batch_size=64, mul =3):
  value_maxlen, tokenizer = input_init
  while True:
      each_size = int(batch_size/2)
      # Shuffle index of link_data
      link_data = [link_data[index] for index in np.random.choice(len(link_data), len(link_data), replace=False)]
      for iter in range(int(len(link_data)/each_size)):
          # Split data by batch size and randomly select non_link_data: 1/2 for link data, 1/2 for unlink data
          link_X = link_data[iter*each_size:(iter+1)*each_size]
          non_link_X = [non_link_data[index] for index in np.random.choice(len(non_link_data), each_size*mul, replace=False)]
          
          # Create X by tokenizing and padding X
          X = np.array(link_X + non_link_X)
          tokenized_A = tokenizer.texts_to_sequences(X[:, 0])
          tokenized_B = tokenizer.texts_to_sequences(X[:, 1])
          padded_A = pad_sequences(tokenized_A, maxlen=value_maxlen, truncating="post")
          padded_B = pad_sequences(tokenized_B, maxlen=value_maxlen, truncating="post")
          
          # Create label y
          link_y = np.vstack([np.zeros(len(link_X)), np.ones(len(link_X))]).T
          non_link_y = np.vstack([np.ones(len(link_X)), np.zeros(len(link_X))]).T
          y = np.concatenate([link_y, non_link_y])
          
          if add_feature!=None:
            # Create other features
            link_other_X = link_other_features[iter*each_size:(iter+1)*each_size]
            non_link_other_X = [non_link_other_features[index] for index in np.random.choice(len(non_link_data), each_size, replace=False)]
            other_features = np.array(link_other_X + non_link_other_X)

          index = np.random.choice(batch_size, batch_size, replace=False)
          if add_feature!=None:
            yield [padded_A[index], padded_B[index], other_features], y[index]
          else:
            yield [padded_A[index], padded_B[index]], y[index]

"""## Model"""

def return_model(input_init, add_feature):
  value_maxlen, tokenizer = input_init
  inputs_A = keras.Input(shape=(value_maxlen), name="input_a")
  inputs_B = keras.Input(shape=(value_maxlen), name="input_b")

  if add_feature==1 or add_feature==2:
    inputs_C = keras.Input(shape=(1), name="input_c")
  else:
    inputs_C = keras.Input(shape=(2), name="input_c")

  # Deep Learning model's structure
  embedding_layer = keras.layers.Embedding(len(tokenizer.word_counts) + 1, 200, embeddings_initializer='uniform', name="embedding")
  rnn_layer = keras.layers.GRU(200, name="gru")
  flatten_layer = keras.layers.Flatten(name="flatten")
  dense_1_layer = keras.layers.Dense(200, activation="relu", name="dense_1")
  output_layer = keras.layers.Dense(2, activation="softmax", name="dense_output")

  # Embedding
  emb_A = embedding_layer(inputs_A)
  emb_B = embedding_layer(inputs_B)
  # RNN
  rnn_A = rnn_layer(emb_A)
  rnn_B = rnn_layer(emb_B)

  if add_feature==None:
  
    # Concat two embedded inputs
    X = tf.concat([flatten_layer(rnn_A), flatten_layer(rnn_B)], axis=1)
  
    dense_1_X = dense_1_layer(X)
  
    outputs = output_layer(dense_1_X)
  
    model = keras.Model(inputs=[inputs_A, inputs_B], outputs=outputs)
    model.compile(optimizer="Adam", loss="mse", metrics=["categorical_accuracy"])
  
  else:
  
    # Concat two embedded inputs
    X = tf.concat([flatten_layer(rnn_A), flatten_layer(rnn_B), inputs_C], axis=1)
  
    dense_1_X = dense_1_layer(X)
  
    outputs = output_layer(dense_1_X)
  
    model = keras.Model(inputs=[inputs_A, inputs_B, inputs_C], outputs=outputs)
    model.compile(optimizer="Adam", loss="mse", metrics=["categorical_accuracy"])
  
  model.summary()

  return model

def train_model(model_params, init_input, add_feature, links_train, non_links_train, links_other_features_train = None, non_links_other_features_train = None):
  steps_per_epoch, epochs, batch_size = model_params
  value_maxlen, tokenizer, model = init_input
  if add_feature!=None:
    model.fit(generate_input([value_maxlen, tokenizer], add_feature, links_train, non_links_train, links_other_features_train, non_links_other_features_train, batch_size = batch_size), 
              steps_per_epoch=steps_per_epoch, 
              epochs=epochs,
              shuffle=False,
              verbose = 1)
  else:
    model.fit(generate_input([value_maxlen, tokenizer], add_feature, links_train, non_links_train, batch_size = batch_size), 
            steps_per_epoch=steps_per_epoch, 
            epochs=epochs,
            shuffle=False,
            verbose = 1)

"""## Test Model"""

def get_data_pairs(input, add_feature):
    pair, label, createds, updateds, texts = input
    data = []
    labels = []
    other_features = []

    # Get link_data_sample
    for index in tqdm(range(len(pair))):
        p = pair[index]
        u = int(p[0])
        v = int(p[1])
        input_A = texts[u]
        input_B = texts[v]
        data.append([input_A, input_B])
        labels.append(label[index])
        if add_feature != None:
          cre_u = createds[u]
          cre_v = createds[v]
          update_v = updateds[v]
          cre_cre = abs((cre_u - cre_v).days)
          cre_up = abs((cre_u - update_v).days)
          if add_feature==1:
            other_features.append([cre_cre])
          else:
            if add_feature==2:
              other_features.append([cre_up])
            else:
              other_features.append([cre_cre, cre_up])
        else:
          other_features = None
    if add_feature!=None:
      other_features = np.array(other_features)
    return data, labels, other_features

"""## Recommend"""

def model_predict(init_input, data_test, labels_test, other_features):
  model, value_maxlen, tokenizer = init_input
  y_s = np.empty((2,2))
  pred_s = np.empty((2,2))

  each_size = len(data_test) #all dataset
  
  t = 0
  while t<each_size:
    if t+4096 < each_size:
      data_X = data_test[t:t+4096]
    else:
      data_X = data_test[t:]

    X = np.array(data_X)
    tokenized_A = tokenizer.texts_to_sequences(X[:, 0])
    tokenized_B = tokenizer.texts_to_sequences(X[:, 1])
    padded_A = pad_sequences(tokenized_A, maxlen=value_maxlen, truncating="post")
    padded_B = pad_sequences(tokenized_B, maxlen=value_maxlen, truncating="post")
    
    # Create label y
    if t+4096 < each_size:
      y = labels_test[t:t+4096]
    else:
      y = labels_test[t:]

    if type(other_features) is np.ndarray:
      # Create features
      if t+4096 < each_size:
        test_features = other_features[t:t+4096]
      else:
        test_features = other_features[t:]
      pred = model.predict([padded_A, padded_B, test_features])
    else:
      pred = model.predict([padded_A, padded_B])
    
    y_s = np.concatenate([y_s, y])
    pred_s = np.concatenate([pred_s, pred])

    t+=4096

    print(t,'/',each_size)

  # Delete empty value in y_s and pred_s
  y_s = y_s[2:]
  pred_s = pred_s[2:]

  # Get label
  y_s = np.argmax(y_s, axis=1)

  pred_proba = np.array(pred_s)[:,1] # Proba of having link

  pred_s = np.argmax(pred_s, axis=1)

  return y_s, pred_s, pred_proba

"""### Evaluate"""

def evaluate(y_s, pred_s):
  m = tf.keras.metrics.Accuracy()
  m.update_state(y_s, pred_s)
  print(m.result().numpy())

  from sklearn.metrics import confusion_matrix, classification_report
  print("Confusion maxtrix")
  print(confusion_matrix(y_s, pred_s))
  print(classification_report(y_s, pred_s, digits= 2))

"""### Recommend"""

def recommend_function(createds, test_nodes, test_pair, pred_proba):
  total_size = len(test_nodes)

  recommend_s = []
  for i in range(total_size):
    recommend_s.append([])

  
  # Make dictionary of test_nodes and position of test_nodes in list
  index_dictionary = dict(zip(test_nodes, range(total_size)))


  for iter in tqdm(range(len(test_pair))):
    pair = test_pair[iter]
    u = int(pair[0])
    v = int(pair[1])
    if abs((createds[u]-createds[v]).days)<=60:
      proba = pred_proba[iter] 
      if u in index_dictionary.keys():
        index_1 = index_dictionary[u]     
        index_2 = v 
        recommend_s[index_1].append((index_2,proba))
      
      if v in index_dictionary.keys():
        index_1 = index_dictionary[v]     
        index_2 = u
        recommend_s[index_1].append((index_2,proba))

  return recommend_s

def Acc(pred, gt):
	acc = 0
	for i, item in enumerate(pred):
		if item in gt:
			acc += 1.0 
			break
	return acc

def MRR(pred, gt):
	mrr = 0
	for i, item in enumerate(pred):
		if item in gt:
			mrr += 1.0/(i+1) 
	return mrr

def Precision_Recall(pred, gt):
  right = 0
  
  for item in gt:
    if item in pred: # relevant
      right+=1

  if len(pred) == 0:
    precision = 0
  else:
    precision = right/len(pred)
  recall = right/len(gt)
  
  return precision, recall

def metrics(recommend, label):
  acc = 0
  mrr = 0
  precision = 0
  recall = 0
  for i in range(0, len(recommend)):
    if len(label[i])!=0:
      acc+=Acc(recommend[i], label[i])
      mrr+=MRR(recommend[i], label[i])
      precision_recall = Precision_Recall(recommend[i], label[i])
      precision+=precision_recall[0]
      recall+=precision_recall[1]
  return acc/(len(recommend)), mrr/(len(recommend)), precision/(len(recommend)), recall/(len(recommend))

"""### List of recommend"""

def get_result(project_name, path, input):
  createds, test_nodes, all_nodes, test_pair, pred_proba = input
  recommend_s = recommend_function(createds, test_nodes, test_pair, pred_proba)
  

  # Sort nodes in pairs
  recommend_s2 = []
  c = 0
  for recommend2 in recommend_s:
    c+=1
    recommend = np.array(sorted(recommend2, key = lambda x: x[1], reverse = True))
    if len(recommend)>0:
      recommend = np.array(recommend[:,0], dtype = int)
    recommend_s2.append(recommend)

  y_test = []

  for i in tqdm(range(len(test_nodes))):
    nodes = []
    for j in range(len(all_nodes)):
      if graph[test_nodes[i], all_nodes[j]][1] !=0 and graph[test_nodes[i], all_nodes[j]][1] !=0:
        nodes.append(all_nodes[j])
    y_test.append(nodes)
  
  f = open(path, "a")
  

  top = 10
  recommend_s = np.array(recommend_s2)

  recommend_s = [i[:top] for i in recommend_s]

  f.write('Top 10:')
  f.write('\n')
  metric = metrics(recommend_s, y_test)
  f.write('Accuracy = ' + repr(metric[0]))
  f.write('\n')
  f.write('MRR = ' + repr(metric[1]))
  f.write('\n')
  f.write('Recall = ' + repr(metric[3]))
  f.write('\n')


  top = 20
  recommend_s = np.array(recommend_s2)
  recommend_s = [i[:top] for i in recommend_s]

  f.write('Top 20:')
  f.write('\n')
  metric = metrics(recommend_s, y_test)
  f.write('Accuracy = ' + repr(metric[0]))
  f.write('\n')
  f.write('MRR = ' + repr(metric[1]))
  f.write('\n')
  f.write('Recall = ' + repr(metric[3]))
  f.write('\n')


  top = 30
  recommend_s = np.array(recommend_s2)

  recommend_s = [i[:top] for i in recommend_s]

  f.write('Top 30:')
  f.write('\n')
  metric = metrics(recommend_s, y_test)
  f.write('Accuracy = ' + repr(metric[0]))
  f.write('\n')
  f.write('MRR = ' + repr(metric[1]))
  f.write('\n')
  f.write('Recall = ' + repr(metric[3]))
  f.write('\n')


  top = 50
  recommend_s = np.array(recommend_s2)
  recommend_s = [i[:top] for i in recommend_s]

  f.write('Top 50:')
  f.write('\n')
  metric = metrics(recommend_s, y_test)
  f.write('Accuracy = ' + repr(metric[0]))
  f.write('\n')
  f.write('MRR = ' + repr(metric[1]))
  f.write('\n')
  f.write('Recall = ' + repr(metric[3]))
  f.write('\n')

  f.close()

"""# Main program

### Start
"""

### Combine 7 string features and 3 time features :
list_project_name = [('MDLSITE', 4000, 12, 50, 256)]
list_choose_feature_string = [['title'], ['description'], ['summary'],
                              ['title', 'description'], ['title', 'summary'],
                                ['title', 'description', 'summary'], ['description', 'summary']]
## 1 = cre_cre
## 2 = cre_up
## 3 = cre_cre + cre_up
list_add_feature = [None, 1, 2, 3]

def Process_function(project_name, add_feature, result_path, input):
  df, createds, updateds, train_nodes, test_nodes, all_nodes, train_pair, train_label, test_pair, test_label = input
  if add_feature==None:
    path = result_path + 'result_1_' + project_name + '.txt'
  else:
      if add_feature==1:
        path = result_path + 'result_2_' + project_name + '.txt'
      else:
        if add_feature==2:
          path = result_path + 'result_3_' + project_name + '.txt'
        else:
          path = result_path + 'result_4_' + project_name + '.txt'

  for choose_feature_string in list_choose_feature_string:
    f = open(path, "a")
    listToStr = ' '.join([str(elem) for elem in choose_feature_string]) 
    listToStr = listToStr + ' ' + repr(add_feature)
    f.write(listToStr)
    f.write('\n')

    f.close()
    
    # Choose maxlen
    value_maxlen = 0
    if len(choose_feature_string)==1:
      if 'title' in choose_feature_string or 'summary' in choose_feature_string:
        value_maxlen = 13
      else:
        value_maxlen = 400
    else:
      if len(choose_feature_string)==2:
        if 'title' in choose_feature_string and 'summary' in choose_feature_string:
          value_maxlen = 26
        else:
          value_maxlen = 413
      else:
        value_maxlen = 426

    # Get features
    all_text = get_string_feature(df, choose_feature_string)

    # Init Tokenizer
    tokenizer = tf.keras.preprocessing.text.Tokenizer()
    tokenizer.fit_on_texts(all_text)

    # Model
    model = return_model([value_maxlen, tokenizer], add_feature)

    if add_feature==None: 
      links_train, non_links_train = get_separated_data_pairs([train_pair, train_label, createds, updateds, all_text], add_feature)
      train_model([steps_per_epoch, epochs, batch_size], [value_maxlen, tokenizer, model], add_feature, links_train, non_links_train)
    else:
      links_train, non_links_train, link_other_features, non_link_other_features = get_separated_data_pairs([train_pair, train_label, createds, updateds, all_text], add_feature)
      train_model([steps_per_epoch, epochs, batch_size], [value_maxlen, tokenizer, model], add_feature, links_train, non_links_train, link_other_features, non_link_other_features)

    model.save(result_path + project_name + '_' + listToStr + '.h5')

    # Test model
    data_test, labels_test, other_features = get_data_pairs([test_pair, test_label, createds, updateds, all_text], add_feature)
    model = keras.models.load_model(result_path + project_name + '_' + listToStr + '.h5')
    y_s, pred_s, pred_proba = model_predict([model, value_maxlen, tokenizer], data_test, labels_test, other_features)
    evaluate(y_s, pred_s)
    np.save(result_path + project_name + '_' + listToStr + '_ys.npy' , y_s)
    np.save(result_path + project_name + '_' + listToStr + '_preds.npy' , pred_s)
    np.save(result_path + project_name + '_' + listToStr + '_pred_proba.npy' , pred_proba)
    get_result(project_name, path, [createds, test_nodes, all_nodes, test_pair, pred_proba])
    break

import multiprocessing
from itertools import product
from contextlib import contextmanager
for project in list_project_name:
  project_name = project[0]
  time_split = project[1]

  # Model params
  steps_per_epoch = project[2]
  epochs = project[3]
  batch_size = project[4]

  # Load dataset
  #path = '/content/drive/My Drive/Jira/Datasets/' + project_name + '/'
  path = '/opt/quynh_data/feature_dataframe/' + project_name + '/'
  df, graph = load_project(path, project_name)

  # Preprocessing
  df = preprocessing(df)

  # Save result link
  #result_path = '/content/drive/My Drive/Jira/Results/' + project_name + '/'
  result_path = '/opt/quynh_data/Results/' + project_name + '/'
  if not os.path.exists(result_path):
      os.makedirs(result_path)
  df.to_csv(result_path + 'preprocessed_df.csv',index=False)

  graph = graph.apply(change_graph)
  graph = graph.values

  # Split data
  createds, updateds = get_time_features(df)
  train_nodes, test_nodes, all_nodes = split_data(createds, graph, time_split)

  # Pairing
  train_pair, train_label = get_pairs(graph, train_nodes, train_nodes)
  test_pair, test_label = get_pairs(graph, test_nodes, all_nodes)

  # Multiprocess need to replace this 2 lines
  for add_feature in list_add_feature:
    Process_function(project_name, add_feature, result_path, [df, createds, updateds, train_nodes, test_nodes, all_nodes, train_pair, train_label, test_pair, test_label])

  # Multiprocess
  # params_1 = [project_name, None, result_path, [df, createds, updateds, train_nodes, test_nodes, all_nodes, train_pair, train_label, test_pair, test_label]]
  # params_2 = [project_name, 1, result_path, [df, createds, updateds, train_nodes, test_nodes, all_nodes, train_pair, train_label, test_pair, test_label]]
  # params_3 = [project_name, 2, result_path, [df, createds, updateds, train_nodes, test_nodes, all_nodes, train_pair, train_label, test_pair, test_label]]
  # params_4 = [project_name, 3, result_path, [df, createds, updateds, train_nodes, test_nodes, all_nodes, train_pair, train_label, test_pair, test_label]]

  # func = Process_function

  # with multiprocessing.Pool(processes=3) as pool:
  #   pool.starmap(func, [params_1, params_2, params_3, params_4])