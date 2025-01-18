import numpy as np
import pandas as pd

# read in pga earnings from ESPN.  Use df[1] when there is a playoff, else use df[0]
# Set global variable on what tourney_nb we are working on

#Global_Tourney_Nb = 1
#df = pd.read_html('https://www.espn.com/golf/leaderboard?tournamentId=401703490')
Global_Tourney_Nb = 2
df = pd.read_html('https://www.espn.com/golf/leaderboard?tournamentId=401703490')

pga_results = df[1]
pga_results['EARNINGS'] = pga_results['EARNINGS'].str.replace(r'[\$,]', '', regex=True)
pga_results['EARNINGS'] = pd.to_numeric(pga_results['EARNINGS'], errors='coerce').fillna(0)
#print(pga_results['EARNINGS'].dtype)

# Rename golfers to so they merge correctly
pga_results['PLAYER'] = np.where(pga_results['PLAYER']=='Ludvig Åberg','Ludvig Aberg', pga_results['PLAYER'])
pga_results['PLAYER'] = np.where(pga_results['PLAYER']=='Séamus Power','Seamus Power', pga_results['PLAYER'])
pga_results['PLAYER'] = np.where(pga_results['PLAYER']=='Nicolai Højgaard','Nicolai Hojgaard', pga_results['PLAYER'])
pga_results['PLAYER'] = np.where(pga_results['PLAYER']=='Rasmus Højgaard','Rasmus Hojgaard', pga_results['PLAYER'])

# Read in rosters
rosters = pd.read_csv(r'C:\Users\tinar\Rosters.csv')

# Read in injuries
injuries = pd.read_csv(r'C:\Users\tinar\Injuries.csv')

# Filter down to just this week's injuries
cur_injuries = injuries[injuries['Tourney_Nb'] == Global_Tourney_Nb]

# Convert to a set for faster lookup
cur_injuries_map = cur_injuries.set_index('Golfer')['Salary'].to_dict()

# Identify injured golfers on each team
for i in range(1, 11):  # For Golfer1 to Golfer10
    golfer_col = f'Golfer{i}'  # Column name for the golfer
    injury_col = f'Injury{i}'  # New column name for injury
    rosters[injury_col] = rosters[golfer_col].map(cur_injuries_map).fillna(0)

# For each team, find the maximum salary of all injured golfers
rosters['Max_Injury_Salary'] = rosters[[f'Injury{i}' for i in range(1,11)]].max(axis=1)
rosters_w_injuries = rosters[rosters['Max_Injury_Salary'] > 0]

# Read salaries
salaries = pd.read_csv(r'C:\Users\tinar\Salaries.csv')

# Join salaries onto the injury sub
rosters = rosters.merge(salaries, how='left', left_on='Golfer0', right_on='Golfer')
rosters.rename(columns={'Salary': 'Sub_Salary'}, inplace=True)
rosters.drop(columns=['Golfer','Owners'], inplace=True)

# attach pga earnings to each golfer, including the injury sub (Golfer0)
for i in range(0,11):
    golfer_col = f"Golfer{i}"
    earnings_col = f"Earnings{i}"
    rosters[earnings_col] = rosters[golfer_col].map(pga_results.set_index("PLAYER")["EARNINGS"])

# If the injury sub salary is highest salaried injured golf (Max_Injury_Salary) then don't count Golfer0 earnings
# Note we also don't count Golfer0 earnings if no golfers on the team are injured, because Max_Injury_Salary = 0
rosters.loc[rosters['Sub_Salary'] > rosters['Max_Injury_Salary'], 'Earnings0'] = 0

# Sum the earnings for the week
rosters['Tourney_Nb'] = Global_Tourney_Nb
rosters['Earn_Sum_Tourney'] = rosters[[f'Earnings{i}' for i in range(11)]].sum(axis=1)
rosters['Earn_Sum_YTD'] = 0

#on the first week of the year, I need to do this (i.e., write out an initial CSV file)
#rosters.to_csv('YTD_Earnings_Detail.csv', index=False)

# read YTD Earnings Detail
# Delete rows where 'Tourney_Nb' is equal to 'Global_Tourney_Nb'.  Do this in case I need to re-run a week
# Append the rosters dataframe to the bottom of the ytd dataframe
ytd_dets = pd.read_csv(r'C:\Users\tinar\YTD_Earnings_Detail.csv')
ytd_dets = ytd_dets[ytd_dets['Tourney_Nb'] != ytd_dets['Global_Tourney_Nb']]
ytd_dets = pd.concat([ytd_dets, rosters],ignore_index=True)

# Sort the DataFrame by 'Team Name' and 'Tourney_Nb'
ytd_dets = ytd_dets.sort_values(by=['Team Name', 'Tourney_Nb'], ascending=[True, True])

# Calculate the running total for 'Earn_Sum_YTD' for each 'Team Name'
ytd_dets['Earn_Sum_YTD'] = ytd_dets.groupby('Team Name')['Earn_Sum_Tourney'].cumsum()
ytd_dets.to_csv('YTD_Earnings_Detail.csv', index=False)

golfer_names = [f'Golfer{i}' for i in range(0,11)]
df_golfers = ytd_dets[['Tourney_Nb','Team Name'] + golfer_names]

golfer_earnings = [f'Earnings{i}' for i in range(0,11)]
df_earnings = ytd_dets[['Tourney_Nb','Team Name'] + golfer_earnings]
df_earnings = df_earnings.rename(columns={f'Earnings{i}': f'Golfer{i}' for i in range(0,11)})

df_ytd_dets = pd.concat([df_golfers, df_earnings],ignore_index=True)
df_ytd_dets = df_ytd_dets.sort_values(by=['Tourney_Nb','Team Name'], ascending=[True,True])
df_ytd_dets = df_ytd_dets.rename(columns={'Golfer0': 'InjurySub'})
df_ytd_dets = df_ytd_dets.fillna("")
df_ytd_dets = df_ytd_dets.replace(0,"")
df_ytd_dets.to_csv('YTD_Details_For_Web.csv', index=False)
