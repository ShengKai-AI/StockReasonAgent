import akshare as ak

info_df = ak.stock_individual_info_em(symbol="600000")
info_dict = dict(zip(info_df['item'], info_df['value']))
df = ak.stock_hot_keyword_em(symbol="SH600000")

print(df)