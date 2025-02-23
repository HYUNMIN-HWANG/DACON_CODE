from tkinter import N
import pandas as pd
import random
import os
import numpy as np
import pickle

from sklearn.linear_model import LinearRegression
from sklearn.multioutput import MultiOutputRegressor
import sklearn.metrics as metrics

import matplotlib.pyplot as plt

import xgboost as xgb

DATA_PATH = 'D:\\Data\\LGAI_AutoDriveSensors\\'

def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
seed_everything(42) # Seed 고정

# DATA
train_df = pd.read_csv(DATA_PATH + 'train.csv')

train_x = train_df.filter(regex='X') # Input : X Featrue
train_y = train_df.filter(regex='Y') # Output : Y Feature

###############################################
# X2 : 스크류 삽입 깊이&방열 재료 1 무게
# Y2 : 신호대 잡음비 2 ~ 7
# 상관계수가 높은 피쳐들끼리 따로 훈련
train_x_2 = train_x.loc[:,['X_19','X_20','X_21','X_22','X_03']]
train_y_2 = train_y.loc[:,['Y_08','Y_09','Y_10','Y_12','Y_13','Y_14']]
###############################################


# DATA Preprocessing
def drop_columns(x, cols) : 
    return x.drop(cols, axis='columns')

def group_mean(x, cols) :
    x_cols = x.loc[:,cols]
    cols_means = x_cols.mean(axis='columns')
    return cols_means

def add_col(x, col_name, value) :
    x[col_name] = value

def make_mean_col(x, cols, col_name) :
    cols_mean = group_mean(x, cols)
    x = drop_columns(x, cols)
    add_col(x, col_name, cols_mean)
    return x

def IQR_except_outlier(col) : 
    Q3, Q1 = np.percentile(col, [75, 25])
    IQR = Q3 - Q1
    lower, upper = Q1-1.5*IQR, Q3+1.5*IQR
    data_low_idx = col[lower > col].index
    data_upper_idx = col[upper < col].index
    execpt_outlier = col[(lower < col) & (upper > col)]

    # outlier를 뺀 값들의 min과 max 값으로 대체함
    min = execpt_outlier.min()
    max = execpt_outlier.max()

    col[data_low_idx] = min
    col[data_upper_idx] = max

    return col

def standardization (data) :
    # z = (x - mean())/std()
    return (data - np.mean(data, axis=0)) / np.std(data, axis=0)

def preprocessing_x (x_data) : 
    # 1차, 2차, 3차 4차 검사 통과 여부 칼럼 제거함 (모두 동일한 값 1, 모두 통과함)
    pass_columns = ['X_04','X_23','X_47','X_48']
    x_data = drop_columns(x_data, pass_columns)

    # 안테나 패드 위치 평균 칼럼 만들기 'X_57'
    x_data = make_mean_col(x_data, ['X_14','X_15','X_16','X_17','X_18'], 'X_57')
    # n번 스크류 삽입 깊이 평균 칼럼 만들기 'X_58'
    x_data = make_mean_col(x_data, ['X_19','X_20','X_21','X_22'], 'X_58')
    # 커넥터 핀 치수 평균 칼럼 만들기 'X_59'
    x_data = make_mean_col(x_data, ['X_24','X_25','X_26','X_27','X_28','X_29'], 'X_59')
    # 스크류 삽입 깊이 n 평균 칼럼 만들기 'X_60'
    # IQR 사용하여 이상치 처리, 이상치를 제거했을 때의 min과 max 값으로 대체
    x_data.loc[:,'X_30'] = IQR_except_outlier(x_data.loc[:,'X_30'].copy())
    x_data.loc[:,'X_31'] = IQR_except_outlier(x_data.loc[:,'X_31'].copy())
    x_data.loc[:,'X_32'] = IQR_except_outlier(x_data.loc[:,'X_32'].copy())
    x_data.loc[:,'X_33'] = IQR_except_outlier(x_data.loc[:,'X_33'].copy())
    x_data = make_mean_col(x_data, ['X_30','X_31','X_32','X_33'], 'X_60')
    # 스크류 체결 시 분당 회전 수 평균 칼럼 만들기 'X_61'
    x_data = make_mean_col(x_data, ['X_34','X_35','X_36','X_37'], 'X_61')
    # 하우징 PCB 안착부 평균 칼럼 만들기 'X_62'
    x_data = make_mean_col(x_data, ['X_38','X_39','X_40'], 'X_62')
    # 레이돔 치수 평균 칼럼 만들기 'X_63'
    x_data = make_mean_col(x_data, ['X_41','X_42','X_43','X_44'], 'X_63')
    # RF 부붙 SMT 납 량 평균 칼럼 만들기 'X_64'
    x_data = make_mean_col(x_data, ['X_50','X_51','X_52','X_53','X_54','X_55','X_56'], 'X_64')
    # 방열 재료 2,3 무게 평균 칼럼 만들기 'X_65'
    x_data = make_mean_col(x_data, ['X_10','X_11'], 'X_65')
    # PCB 체결 시 단계별 누름량 이상치 제거
    x_data.loc[:,'X_06'] = IQR_except_outlier(x_data.loc[:,'X_06'].copy())
    # 방열 재료 면적 평균 칼럼 만들기 'X_66'
    x_data.loc[:,'X_07'] = IQR_except_outlier(x_data.loc[:,'X_07'].copy())
    x_data.loc[:,'X_08'] = IQR_except_outlier(x_data.loc[:,'X_08'].copy())
    x_data.loc[:,'X_09'] = IQR_except_outlier(x_data.loc[:,'X_09'].copy())
    x_data = make_mean_col(x_data, ['X_07','X_08','X_09'], 'X_66')
    # Cal 투입 전 대기 시간 이상치 제거
    x_data.loc[:,'X_49'] = IQR_except_outlier(x_data.loc[:,'X_49'].copy())

    # 표준화
    x_data = standardization(x_data)
    # >> train_x.shape (39607, 22)
    return x_data

def del_outlier(x, y, col) :
    Q3, Q1 = np.percentile(y.loc[:,col], [75, 25])
    IQR = Q3 - Q1
    lower, upper = Q1-1.5*IQR, Q3+1.5*IQR
    outlier_idx = y[(lower > y.loc[:,col]) | (upper < y.loc[:,col])].index 
    x = x.drop(x.index[outlier_idx])
    y = y.drop(y.index[outlier_idx])
    return x, y


train_x_stand = preprocessing_x(train_x)
train_x_stand, train_y = del_outlier(train_x_stand, train_y, 'Y_04')

# XGB Model Fit
xgb_regressor = xgb.XGBRegressor(
                        n_estimators=200, 
                        learning_rate=0.08,
                        gamma = 0, 
                        subsample=0.75, 
                        colsample_bytree = 1, 
                        max_depth=7) 

xgb = MultiOutputRegressor(xgb_regressor).fit(train_x_stand, train_y)
print('Train Done.')

with open(DATA_PATH+'weights/xgbmodel8.pkl','wb') as f:
    pickle.dump(xgb,f)

# Inference
test_x = pd.read_csv(DATA_PATH + 'test.csv').drop(columns=['ID'])
test_x_stand = preprocessing_x(test_x)

preds = xgb.predict(test_x_stand)
print('Inference Done.')

###############################################
# X2 : 스크류 삽입 깊이&방열 재료 1 무게
# Y2 : 신호대 잡음비 2 ~ 7
train_x2_stand = standardization(train_x_2)
xgb2 = MultiOutputRegressor(xgb_regressor).fit(train_x2_stand, train_y_2)
print('Train 2 Done.')

with open(DATA_PATH+'weights/xgbmodel8-2.pkl','wb') as f:
    pickle.dump(xgb2,f)

# Inference
test_x = pd.read_csv(DATA_PATH + 'test.csv').drop(columns=['ID'])
test_x_2 = test_x.loc[:,['X_19','X_20','X_21','X_22','X_03']]
test_x_stand = standardization(test_x_2)

preds_2 = xgb2.predict(test_x_stand)
print('Inference 2 Done.')

# data 1에 있던 값들을 data 2 값으로 바꾼다.
preds[:,7:10] = preds_2[:,:3].copy()
preds[:,11:] = preds_2[:,3:].copy()
###############################################
# Submit
submit = pd.read_csv(DATA_PATH +'sample_submission.csv')

for idx, col in enumerate(submit.columns):
    if col=='ID':
        continue
    submit[col] = preds[:,idx-1]
print('Submit Done.')

print(submit.head())
submit.to_csv(DATA_PATH + 'submit/submit_xgb8.csv', index=False)

################################################### TEST

def lg_nrmse(gt, preds):
    # 각 Y Feature별 NRMSE 총합
    # Y_01 ~ Y_08 까지 20% 가중치 부여
    all_nrmse = []
    for idx in range(1,14): # ignore 'ID'
        rmse = metrics.mean_squared_error(gt.iloc[:,idx], preds[:,idx], squared=False)
        nrmse = rmse/np.mean(np.abs(gt.iloc[:,idx]))
        all_nrmse.append(nrmse)
    score = 1.2 * np.sum(all_nrmse[:8]) + 1.0 * np.sum(all_nrmse[8:15])
    return score

print(" ")

score = lg_nrmse(train_y, xgb.predict(train_x_stand))
print(score) 
# 1.3447169728393424

# Y04 이상치인 idx 제거함
# submit_xgb8.csv
# 1.9773575494
