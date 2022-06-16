import os
import shutil
import requests
import traceback
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
## Plot style
plt.style.use('ggplot')
from shapely.geometry import Point
from statsmodels.stats.weightstats import DescrStatsW

def plot_hist(df,save_fig = False,**kwargs):
    # df,file_path,filename,save_fig = True
    """Used to Plot Weighted Histogram of distributions

    Args:
        df (DataFrame): Final DataFrame  
        file_path (str): File Path
        title (str): Title of plot
        max_spacing (_type_): Maximum Allowed Spacing between two stops. Defaults to 3000.
        save_fig (bool, optional): Field to save the generated figure. Defaults to True.
    """ 
    if "max_spacing" not in kwargs.keys():
        max_spacing = 3000
        print("Using max_spacing = 3000")
    else:
        max_spacing = kwargs['max_spacing']
    if "ax" in kwargs.keys():
        ax = kwargs['ax']
    else:
        fig, ax = plt.subplots(figsize=(10,8))
    data = np.hstack([np.repeat(x, y) for x, y in zip(df['distance'], df.traversals)])
    sns.histplot(data,binwidth=50,kde=True,ax=ax)
    plt.xlim([0,max_spacing])
    plt.xlabel('Stop Spacing [m]')
    plt.ylabel('Density - Traversal Weighted')
    plt.title("Histogram of Spacing")
    if "title" in kwargs.keys():
        plt.title(kwargs['title'])
    if save_fig == True:
        assert "file_path" in kwargs.keys(), "Please pass in the `file_path`"
        plt.savefig(kwargs['file_path'], dpi=200)
    plt.show()
    plt.close(fig)
    return ax

def summary_stats(df,folder_path,filename,b_day,link,bounds,max_spacing = 3000):
    """Generate a report of summary statistics for the gtfs file

    Args:
        df (DataFrame): DataFrame
        folder_path (str): Folder Path
        filename (str): Filename
        b_day (date): Busiest Day
        link (str): Download URL
        bounds (tuple): Lat Long bounds
        max_spacing (int, optional): Maximum Allowed Spacing between two consecutive stops. Defaults to 3000.
    """
    weighted_stats = DescrStatsW(df["distance"], weights=df.traversals, ddof=0)
    quant = weighted_stats.quantile([0.25,0.5,0.75],return_pandas=False)
    percent_spacing = round(df[df["distance"] > max_spacing]['traversals'].sum()/df['traversals'].sum() *100,3)
    csv_path = os.path.join(folder_path,'summary.csv')
    with open(csv_path, 'w',encoding='utf-8') as f:
        f.write('Name,'+str(filename)+'\n')
        f.write('Busiest Day,'+str(b_day)+'\n')
        f.write('Link,'+str(link)+'\n')
        f.write('Min Latitude,'+str(bounds[0][1])+'\n')
        f.write('Min Longitude,'+str(bounds[0][0])+'\n')
        f.write('Max Latitude,'+str(bounds[1][1])+'\n')
        f.write('Max Longitude,'+str(bounds[1][0])+'\n')
        f.write('Mean,'+str(round(weighted_stats.mean,3))+'\n')
        f.write('Std,'+str(round(weighted_stats.std,3))+'\n')
        f.write('25 % Quantile,'+str(round(quant[0],3))+'\n')
        f.write('50 % Quantile,'+str(round(quant[1],3))+'\n')
        f.write('75 % Quantile,'+str(round(quant[2],3))+'\n')
        f.write('No of Segments,'+str(len(df))+'\n')
        f.write('No of Routes,'+str(len(df.route_id.unique()))+'\n')
        f.write('No of Traversals,'+str(sum(df.traversals))+'\n')
        f.write('Max Spacing,'+str(max_spacing)+'\n')
        f.write('% Segments w/ spacing > max_spacing,'+str(percent_spacing))
        f.close()
    summary_df = pd.read_csv(csv_path)
    summary_df.set_index(summary_df.columns[0],inplace=True)
    summary_df = summary_df.T
    summary_df.to_csv(csv_path,index = False)

def export_segements(df,file_path,output_format, geometry = True):
    """Write the DataFrame as csv and geojson

    Args:
        df (DataFrame): DataFrame
        file_path (str): Output File Path
    """
    ## Output to GeoJSON
    if output_format == 'geojson':
        df.to_file(file_path+'.json', driver="GeoJSON")
    elif output_format == 'csv':
        s_df = df[['route_id','segment_id','stop_id1','stop_id2','distance','traversals','geometry']].copy()
        geom_list =  s_df.geometry.apply(lambda g: np.array(g.coords))
        s_df['start_point'] = [Point(g[0]).wkt for g in geom_list]
        s_df['end_point'] = [Point(g[-1]).wkt for g in geom_list]
        s_df['start_lon'] = [g[0][0] for g in geom_list]
        s_df['start_lat'] = [g[0][1] for g in geom_list]
        s_df['end_lon'] = [g[-1][0] for g in geom_list]
        s_df['end_lat'] = [g[-1][1] for g in geom_list]
        sg_df = s_df[['route_id','segment_id','stop_id1','stop_id2','distance','traversals','start_point','end_point','geometry']]
        if geometry == True:
            ## Output With LS
            sg_df.to_csv(file_path+'.csv',index = False)
        else:
            d_df = s_df[['route_id','segment_id','stop_id1','stop_id2','start_lat','start_lon','end_lat','end_lon','distance','traversals']]
            ## Output without LS
            d_df.to_csv(file_path+'.csv',index = False)


def process(pipeline_gtfs,row,max_spacing):
    """

    Args:
        pipeline_gtfs (function): Pipeline that will return processed dataframe
        row (row): row in sources_df
        max_spacing (int): Maximum Allowed Spacing between two consecutive stops.
    """
    filename = row['file_name']
    url = row['urls.direct_download']
    bounds = [[row['location.bounding_box.minimum_longitude'],row['location.bounding_box.minimum_latitude']],[row['location.bounding_box.maximum_longitude'],row['location.bounding_box.maximum_latitude']]]
    print(filename)
#     pipeline_gtfs(filename,url,bounds,max_spacing)
    try:
        return pipeline_gtfs(filename,url,bounds,max_spacing)
    except:
        traceback.print_exc()
        folder_path  = os.path.join('output_files',filename)
        return failed_pipeline("Failed",filename,folder_path)

def failed_pipeline(message,filename,folder_path):
    """Used to terminate the process and return error message

    Args:
        message (str): Failure cause
        filename (str): Filename
        folder_path (str): Folder path

    Returns:
        str: Failure Message
    """
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    return message + filename

def download_write_file(url,folder_path):
    """Function to download the gtfs file from url and save it in a folder

    Args:
        url (str): URL to download
        folder_path (str): Folder path

    Returns:
        str: Path to downloaded file
    """
    ## Download file from URL
    r = requests.get(url, allow_redirects=True)
    gtfs_file_loc = folder_path+"/gtfs.zip"
    
    ## Write file locally
    file = open(gtfs_file_loc, "wb")
    file.write(r.content)
    file.close()
    return gtfs_file_loc