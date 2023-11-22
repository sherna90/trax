# -*- coding: utf-8 -*-
"""Copia de Hierarchical-Model.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1kEFVgGlWTVyk3QeB3Aiwx1QF3vgfnUGK

Data Download
"""

"""install=True
if install:
  !wget https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip
  !unzip beijing+multi+site+air+quality+data.zip
  !unzip PRSA2017_Data_20130301-20170228.zip
"""
"""Libraries"""

"""Esto tiene que ser ejecutado en este orden"""
import pandas as pd
import numpy as np
np.linalg._umath_linalg._ilp64=True
import optax
import datetime
import jax
import jax.numpy as jnp
from flax import linen as nn
from functools import partial

#!pip install distrax

import distrax
from sklearn import metrics

"""Variables"""

pd.options.mode.chained_assignment = None  # default='warn'
wind_direction={'NNW': 337.5, 'N': 0, 'NW': 315.0, 'NNE': 22.5, 'ENE': 67.5, 'E': 90, 'NE': 45.0, 'W': 270, 'SSW': 202.5, 'WSW': 247.5, 'SE': 135.0, 'WNW': 292.5, 'SSE': 157.5, 'ESE': 112.5, 'S': 180, 'SW': 225.0}
wdn={i:(wind_direction[i]-min(wind_direction.values()))/(max(wind_direction.values())-min(wind_direction.values())) for i in wind_direction}
day=24*60*60
future=6
past=6

"""CSV DATA EXTRACTION"""

import glob

path = 'PRSA_Data_20130301-20170228/'
csv_files = glob.glob(path + "/*.csv")

# Read each CSV file into DataFrame
# This creates a list of dataframes
df_list = [pd.read_csv(file) for file in csv_files]

def pre_process(df):
    df['date_time']=pd.to_datetime(df[['year', 'month', 'day','hour']])
    df.drop(columns=['year', 'month', 'day','hour','No'],inplace=True)
    df.set_index('date_time',inplace=True)
    return df

df_preprocessed=[pre_process(df) for df in df_list]
df_group=pd.concat(df_preprocessed)

"""Data Processing"""

import math
def train_test_split(data,split_fraction,feature_keys):
    data=data[feature_keys]
    data.drop(['wd'],axis='columns',inplace=True)
    train_split = int(split_fraction * int(data.shape[0]))
    data_mean = data[:train_split].mean(axis=0)
    data_std = data[:train_split].std(axis=0)
    data = (data - data_mean) / data_std
    train_data = data.iloc[0 : train_split - 1]
    val_data = data.iloc[train_split:]
    return train_data,val_data
def train_test_split_onehot(data,split_fraction,feature_keys):
    data=data[feature_keys]
    for direction in wdn:
      data[direction]=[1 if k==direction else 0 for k in data['wd']]
    data.drop(['wd'],axis='columns',inplace=True)
    train_split = int(split_fraction * int(data.shape[0]))
    data_mean = data[:train_split].mean(axis=0)
    data_std = data[:train_split].std(axis=0)
    data = (data - data_mean) / data_std
    train_data = data.iloc[0 : train_split - 1]
    val_data = data.iloc[train_split:]
    return train_data,val_data
def train_test_split_cyclical(data,split_fraction,feature_keys):
    data=data[feature_keys]
    wd=[wdn[x] for x in data['wd']]
    timestamp_s=pd.to_datetime(data.index).map(datetime.datetime.timestamp)
    data['day_sin']=(np.sin(timestamp_s* (2*np.pi/day))).values
    data['day_cos']=(np.cos(timestamp_s* (2*np.pi/day))).values
    data.drop(['wd'],axis='columns',inplace=True)
    data['wd']=wd
    train_split = int(split_fraction * int(data.shape[0]))
    data_mean = data[:train_split].mean(axis=0)
    data_std = data[:train_split].std(axis=0)
    data = (data - data_mean) / data_std
    train_data = data.iloc[0 : train_split - 1]
    val_data = data.iloc[train_split:]
    return train_data,val_data
def train_test_split_ordinal(data,split_fraction,feature_keys):
    data=data[feature_keys]
    wd=[wdn[x] for x in data['wd']]
    timestamp_s=pd.to_datetime(data.index)
    data['day']=[date.day for date in timestamp_s]
    data['month']=[date.month for date in timestamp_s]
    data['year']=[date.year for date in timestamp_s]
    data['hour']=[date.hour for date in timestamp_s]
    data['wd']=wd
    train_split = int(split_fraction * int(data.shape[0]))
    data_mean = data[:train_split].mean(axis=0)
    data_std = data[:train_split].std(axis=0)
    data = (data - data_mean) / data_std
    train_data = data.iloc[0 : train_split - 1]
    val_data = data.iloc[train_split:]
    return train_data,val_data
def train_test_split_cyclical_only(data,split_fraction,feature_keys):
    data=data[feature_keys]
    timestamp_s=pd.to_datetime(data.index).map(datetime.datetime.timestamp)
    data['day_sin']=(np.sin(timestamp_s* (2*np.pi/day))).values
    data['day_cos']=(np.cos(timestamp_s* (2*np.pi/day))).values
    data['wd_sin']=[math.sin(wind_direction[x]) for x in data["wd"]]
    data['wd_cos']=[math.cos(wind_direction[x]) for x in data["wd"]]
    data.drop(['wd'],axis='columns',inplace=True)
    train_split = int(split_fraction * int(data.shape[0]))
    data_mean = data[:train_split].mean(axis=0)
    data_std = data[:train_split].std(axis=0)
    data = (data - data_mean) / data_std
    train_data = data.iloc[0 : train_split - 1]
    val_data = data.iloc[train_split:]
    return train_data,val_data

"""Create Batch"""

def create_batch(data,lag,future):
    df_lag=pd.concat([data[:-future].shift(i) for i in range(lag-1,-1,-1)],axis=1).dropna()
    #df_lag.columns=['pm_'+str(i) for i in range(lag,-1,1)]
    X=df_lag.values
    y=data[future+lag-1:].values
    return X,y

def create_batch_multistep(df,lag,future,feature=None):
    if feature is None:
        data=df
    else:
        data=df[feature]
    df_lag=pd.concat([data[:-future].shift(i) for i in range(lag-1,-1,-1)],axis=1).dropna()
    df_future=pd.concat([data[lag-1:].shift(-i) for i in range(1,future+1)],axis=1).dropna()
    #df_lag.columns=['pm_'+str(i) for i in range(lag,-1,1)]
    X=df_lag.values
    y=df_future.values
    return X,y

"""MODEL"""

import jax
import jax.numpy as jnp

def get_dataloader(X,y,batch_size,key,axis=0):
    num_train=X.shape[axis]
    indices = jnp.array(list(range(0,num_train)))
    indices=jax.random.permutation(key,indices)
    for i in range(0, len(indices),batch_size):
        batch_indices = jnp.array(indices[i: i+batch_size])
        yield X[:,batch_indices,:,:], y[:,batch_indices]

class LSTM(nn.Module):

    @nn.remat
    @nn.compact
    def __call__(self, X_batch):
        carry,x=nn.RNN(nn.LSTMCell(32),return_carry=True)(X_batch)
        #carry,x=nn.RNN(nn.LSTMCell(32),return_carry=True)(x)
        x=nn.elu(x)
        x=nn.Dense(future)(x)
        return x[:,-1,:]


def reparameterize(params):
    mu = params['mu']
    sigma = jax.tree_map(lambda p : jnp.exp(0.5*p),params['log_std'])
    eps = params['eps']
    #eps=jax.tree_map(lambda p: jax.random.normal(key=jax.random.PRNGKey(np.random.randint(42)),shape=p.shape), params['eps'])
    model_params = jax.tree_map(lambda m,e,s : m+e*s,mu,eps,sigma)
    return model_params

def log_likelihood(params, x, y):
    model_params=reparameterize(params)
    preds = jax.vmap(model.apply, (0, 0))(model_params, jnp.array(x))
    sigmas = jax.vmap(model.apply, (None, 0))(params['log_aleatoric'], jnp.array(x))
    sigmas=jax.tree_map(lambda p: jax.nn.softplus(p),sigmas)
    return -1.0*jnp.mean(distrax.Normal(preds,sigmas).log_prob(y).sum(axis=-1))
    #return (jnp.mean(optax.l2_loss(y,preds).sum(axis=1)))

def log_prior(params):
    def flatten(params):
        squared=jax.tree_map(lambda p: distrax.Normal(0.0,1.0).log_prob(p).sum(), params)
        flattten_squared=jnp.sum(jnp.stack(jax.tree_util.tree_leaves(squared['params'])))
        return flattten_squared
    squared_mu=flatten(params['mu'])
    squared_noise=flatten(params['eps'])
    squared_std=flatten(params['log_std'])
    return (squared_std+squared_noise+squared_mu)

def log_post(params,batch,labels):
    n_data=batch.shape[0]
    return -1./n_data*log_prior(params) + log_likelihood(params,batch,labels)

grad_log_post=jax.jit(jax.grad(log_likelihood))

@partial(jax.jit, static_argnums=(3,4))
def sgld_kernel_momemtum(key, params, momemtum,grad_log_post, dt, X, y_data):
    gamma,eps=0.9,1e-6
    key, subkey = jax.random.split(key, 2)
    grads = grad_log_post(params, X, y_data)
    squared_grads=jax.tree_map(lambda g: jnp.square(g),grads)
    momemtum=jax.tree_map(lambda m,s : gamma*m+(1-gamma)*s,momemtum,squared_grads)
    noise=jax.tree_map(lambda p: jax.random.normal(key=subkey,shape=p.shape), params)
    params=jax.tree_map(lambda p, g,m,n: p-0.5*dt*g/(m+eps)+jnp.sqrt(dt)*n, params, grads,momemtum,noise)
    return key, params,momemtum

def sgld(key,log_post, grad_log_post, num_samples,
                             dt, x_0,X_train_datasets,y_train_datasets,batch_size,
                             test_data=None):
    samples = list()
    loss=list()
    param = x_0
    key_data, key_model = jax.random.split(key, 2)
    momemtum=jax.tree_map(lambda p:jnp.zeros_like(p),param)
    key_data_batch=jax.random.split(key_data, num_samples)
    for i in range(num_samples):
        train_data=get_dataloader(X_train_datasets,y_train_datasets,batch_size,key_data_batch[i],axis=1)
        for _,(X_batch, y_batch) in enumerate(train_data):
            key_model,param,momemtum = sgld_kernel_momemtum(key_model, param,momemtum, grad_log_post, dt, X_batch, y_batch)
        loss.append(log_post(param,X_batch,y_batch))
        samples.append(param)
        if (i%(num_samples//10)==0):
            print('iteration {0}, loss {1:.2f}'.format(i,loss[-1]))
    return samples,loss

"""DATA TESTING"""

from sklearn import metrics
#MAX VALUE=1023
split_fraction = 0.8
feature_keys=['PM2.5','TEMP','PRES','DEWP','PM10','WSPM','wd']


X_train_datasets=list()
y_train_datasets=list()
X_test_datasets=list()
y_test_datasets=list()
dataset_names=list()
for item_id, gdf in df_group.groupby('station'):
  gdf.fillna(method='ffill',inplace=True)
  train,test=train_test_split_cyclical_only(gdf,split_fraction,feature_keys)
  train.fillna(method='ffill',inplace=True)
  test.fillna(method='ffill',inplace=True)
  train_multi_feature=list()
  test_multi_feature=list()
  for feature in list(train.columns):
    X_train,y_train=create_batch_multistep(train,past,future,feature)
    X_test,y_test=create_batch_multistep(test,past,future,feature)
    train_multi_feature.append(X_train)
    test_multi_feature.append(X_test)
    if feature=='PM2.5':
      y_train_datasets.append(y_train)
      y_test_datasets.append(y_test)
  X_train_datasets.append(np.stack(train_multi_feature,axis=-1))
  X_test_datasets.append(np.stack(test_multi_feature,axis=-1))
  dataset_names.append(item_id)
X_train_datasets=np.stack(X_train_datasets,axis=0)
y_train_datasets=np.stack(y_train_datasets,axis=0)
X_test_datasets=np.stack(X_test_datasets,axis=0)
y_test_datasets=np.stack(y_test_datasets,axis=0)



key=jax.random.PRNGKey(0)
key_model,key_data=jax.random.split(key,2)
batch_size=256
model=LSTM()
n_groups=X_train_datasets.shape[0]
features=len(list(train.columns))
inputs = jax.random.randint(key,(batch_size,past,features),0, 10,).astype(jnp.float32)
key_model_init, key_state_init = jax.random.split(key_model, 2)
key_params_mu,key_params_sigma,key_params_eps,key_params_aleatoric=jax.random.split(key_model_init,4)
key_tasks=jax.random.split(key_params_eps,n_groups)

params_noise = jax.vmap(model.init, (0, None))(key_tasks, inputs)
#params_noise=model.init(key_params_eps,inputs)
params_mu=model.init(key_params_mu,inputs)

params_sigma=model.init(key_params_sigma,inputs)
params_aleatoric=model.init(key_params_aleatoric,inputs)
params_sigma=jax.tree_map(lambda p: jax.nn.softplus(p),params_sigma)
params_aleatoric=jax.tree_map(lambda p: jax.nn.softplus(p),params_aleatoric)
#jax.tree_map(lambda p: distrax.Normal(0.0,1.0).sample(seed=key_params_sigma,sample_shape=(1,)),params_mu)


params_pooled = {
    'mu': params_mu,
    'eps': params_noise,
    'log_std': params_sigma,
    'log_sigma': params_aleatoric
}
model_params=reparameterize(params_pooled)
batch_inputs = jax.random.randint(key_data,(n_groups,batch_size,past,features),0, 10,).astype(jnp.float32)

preds = jax.vmap(model.apply, (0, 0))(model_params, batch_inputs)
dt=1e-5

#numero de interaciones
n_iteration=50

samples,loss=sgld(key_data,log_likelihood, grad_log_post, n_iteration,
                      dt, params_pooled,X_train_datasets,y_train_datasets,
                    batch_size,test_data=None)
X_test=X_test_datasets[:,:,:]
model_params=reparameterize(samples[-1])
preds=jax.vmap(model.apply, (0, 0))(model_params, X_test)
X_test=X_test_datasets[:,:,:]
model_params=reparameterize(samples[-1])
preds=jax.vmap(model.apply, (0, 0))(model_params, X_test)
r_metric=list()
rmse_metric=list()
mae_metric=list()

for i in range(n_groups):
  for j in range(future):
    r_squared=metrics.r2_score(preds[i,:,j],y_test_datasets[i,:,j])
    rmse=metrics.mean_squared_error(preds[i,:,j],y_test_datasets[i,:,j],squared=True)
    mae=metrics.mean_absolute_error(preds[i,:,j],y_test_datasets[i,:,j])
    print('Forecast period: {4} task : {0}, RMSE : {1:1.2f}, MAE :{2:1.2f}, R2 :{3:1.2f}'.format(dataset_names[i],rmse,mae,r_squared,j))
  r_squared=metrics.r2_score(preds[i,:,:],y_test_datasets[i,:,:])
  rmse=metrics.mean_squared_error(preds[i,:,:],y_test_datasets[i,:,:],squared=True)
  mae=metrics.mean_absolute_error(preds[i,:,:],y_test_datasets[i,:,:])
  r_metric.append(r_squared)
  rmse_metric.append(rmse)
  mae_metric.append(mae)
  print('task : {0}, RMSE : {1:1.2f}, MAE :{2:1.2f}, R2 :{3:1.2f}'.format(dataset_names[i],rmse,mae,r_squared))
print('-------------------------------------------------------')
print('RMSE : {0:1.2f}, MAE :{1:1.2f}, R2 :{2:1.2f}'.format(np.mean(rmse_metric),np.mean(mae_metric),np.mean(r_metric)))

# baseline RMSE : 1.25, MAE :0.74, R2 :-1.80
