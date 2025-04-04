import json
from fastapi import Depends, FastAPI, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Annotated

import utils.semantic
import utils.experiments
from utils.credentials import User, validate_token_for_loggers_endpoint, validate_token_for_readers_endpoint, validate_token_for_admin_endpoint
from model import connect_to_db, save_json_ld, get_raw_graph_from_db, log_ttl_content, clear_graph, get_logs_list, get_log_info


import logging
import os

# Set up logging
logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
log_file = os.getenv("SERVER_LOG_FILE", "segb_server.log")
# Ensure the logs directory exists
os.makedirs('/logs', exist_ok=True)
file_handler = logging.FileHandler(
    filename=f'/logs/{log_file}',
    mode='a',
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s -> %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger = logging.getLogger("segb_server")
logger.setLevel(getattr(logging, logging_level, logging.INFO))
logger.addHandler(file_handler)

logger.info("Starting SEGB server...")
logger.info("Logging level set to %s", logging_level)

    
class Log(BaseModel):
    log_id: str
    
class Experiment(BaseModel):
    experiment_id: str | None = None
    namespace: str | None = None
    uri: str | None = None

app = FastAPI()

logger.info("Connecting to the database...")
connect_to_db()
logger.info("Database connection established.")

logger.info("SEGB server is now running and ready to accept requests.")

### Endpoints ###
@app.get('/health')
async def default_route(request: Request):
    logger.info("Health check request received from IP: %s", request.client.host)
    return Response(content="The SEGB is working", status_code=status.HTTP_200_OK, media_type="text/plain")

@app.post('/log')
async def save_log(user: Annotated[User, Depends(validate_token_for_loggers_endpoint)], request: Request):
    logger.info(f"Received post for log from IP: {request.client.host} from user {user.name} (username: {user.username})")
    try:
        recieved_data = await request.body()
        recieved_data = recieved_data.decode("utf-8")
        if not recieved_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not recieved data or invalid data"
                )

        origin_ip = request.client.host
        logger.info(f"Received log data from {origin_ip}")
        json_ld_data = None

        try:
            graph = utils.semantic.get_graph_from_ttl(recieved_data)
            logger.debug(f"Graph loaded from received Turtle data")
            json_ld_data = utils.semantic.convert_graph_to_json_ld(graph=graph)
            logger.debug(f"Graph converted to JSON-LD format")
        except Exception as e:
            logger.error(f"Error converting Turtle data to JSON-LD: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not recieved data or invalid data"
                )
        save_json_ld(json_ld_data=json_ld_data)
        logger.info("Log data integrated into the global graph")
        log_ttl_content(recieved_data,origin_ip)
        logger.debug(f"Log registred in history")
        return JSONResponse(content={"message": "Log saved successfully"}, status_code=status.HTTP_201_CREATED)
    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except:
        logger.error("Error saving log data")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
            )

@app.get('/log')
async def get_log(user: Annotated[User, Depends(validate_token_for_admin_endpoint)], request: Request, log: Log = None, log_id: str = None):
    log_id = log.log_id if log else log_id
    if not log_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not recieved log_id via json or query string"
            )
    logger.info(f"Received request for log with ID: {log_id} from IP: {request.client.host} from user {user.name} (username: {user.username})")
    logger.info(f"Received log_id: {log_id}")
    if not log_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not recieved data or invalid data"
            )
    else:
        try:
            log_data = get_log_info(log_id)
            
            if not log_data:
                logger.info(f"Log info not found for ID: {log_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Log info not found"
                    )
        except HTTPException as e:
            logger.error(f"HTTPException: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Error retrieving log: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving log"
                )
    
    return JSONResponse(content=log_data, status_code=status.HTTP_200_OK)

@app.get('/history')
async def get_history(user: Annotated[User, Depends(validate_token_for_admin_endpoint)], request: Request):
    logger.info(f"Received request for history from IP: {request.client.host} from user {user.name} (username: {user.username})")
    try:
        history = get_logs_list()
        logger.debug(f"History retrieved successfully")
        if not history:
            logger.info("No history found")
            response = JSONResponse(content=[], status_code=status.HTTP_204_NO_CONTENT)
        else:
            logger.info("History found")
            response = JSONResponse(content=history, status_code=status.HTTP_200_OK)
        logger.debug(f"Response status code: {response.status_code}")
        return response
    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Error retrieving history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving history: {str(e)}"
        )

@app.get('/query')
async def get_query(user: Annotated[User, Depends(validate_token_for_admin_endpoint)]):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented yet"
    )
    '''
    TODO: check how modifications to the graph are done (or not done),
    because it is loaded "locally" in memory and not loaded again in the database 
    '''

    # if request.is_json:
    #     logger.debug(f"Request body: {request.get_json()}")
    #     args = request.get_json()
    # else:
    #     logger.debug(f"Request arguments: {request.args}")
    #     args = request.args.to_dict()
    # sparql_query = args.get('query')
    # if not sparql_query:
    #     return Response("Missing query parameter", status=400)
    
    # try:
    #     # Retrieve the graph data as in get_graph
    #     json_ld_data = get_raw_graph_from_db()
    #     graph = utils.semantic.get_graph_from_json(json_ld_data)
        
    #     # Execute the SPARQL query using the semantic utils module on the retrieved graph
    #     query_result = utils.semantic.execute_sparql_query(graph, sparql_query)
    #     # TODO: not so simple to parse "any" query result, but we could return the raw result
    #     result = query_result.serialize()
    #     return Response(result, status=200)
    # except Exception as e:
    #     return Response(f"Error executing SPARQL query: {str(e)}", status=500)

@app.get('/graph')
async def get_graph(user: Annotated[User, Depends(validate_token_for_readers_endpoint)], request: Request):
    logger.info(f"Received request for graph from IP: {request.client.host} from user {user.name} (username: {user.username})")
    json_ld_data = None
    turtle_data = None
    try:
        json_ld_data = get_raw_graph_from_db()
        if not json_ld_data:
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
                detail="Empty graph"
            )
        else:    
            graph = utils.semantic.get_graph_from_json(json_ld_data)
            turtle_data = utils.semantic.convert_graph_to_turtle(graph)
            logger.info("Graph retrieved successfully")
            response = PlainTextResponse(content=turtle_data)
            response.headers["Content-Type"] = "text/turtle"
            response.status_code = status.HTTP_200_OK
            return response
    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )
    

@app.delete('/graph')
async def delete_graph(user: Annotated[User, Depends(validate_token_for_admin_endpoint)], request: Request):
    logger.info(f"Received request to delete graph from IP: {request.client.host} from user {user.name} (username: {user.username})")
    origin_ip = request.client.host
    json_ld_data = get_raw_graph_from_db()
    if not json_ld_data:
        logger.info("Empty graph, nothing to delete")
        return PlainTextResponse(content="Empty graph, nothing to delete", status_code=status.HTTP_204_NO_CONTENT)
    deleted = clear_graph(origin_ip)
    if not deleted:
        logger.error("Failed to delete the graph")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete the graph"
        )
    else:
        logger.info("Graph deleted successfully")
        return PlainTextResponse(content="Graph deleted successfully")

@app.get('/experiments')
async def get_experiment(user: Annotated[User, Depends(validate_token_for_readers_endpoint)], request: Request, uri: str = None, namespace: str = None, experiment_id: str = None, experiment: Experiment = None):
    logger.info(f"Received request to get a specific experiment from IP: {request.client.host} from user {user.name} (username: {user.username})")
    uri =  experiment.uri if experiment and experiment.uri else uri
    if uri:
        logger.info(f"Received URI: {uri}")
        # If the URI is provided, we expect it to be a complete URI
        # Preferred option: form of namespace#experiment_id
        # If the URI is provided, namespace and experiment_id are ignored
        namespace, experiment_id = uri.rsplit("#", 1) 
        namespace += "#"
    else:
        # If the URI is not provided, we expect the namespace and experiment_id as separate parameters
        namespace = experiment.namespace if experiment and experiment.namespace else namespace
        experiment_id = experiment.experiment_id if experiment and experiment.experiment_id else experiment_id
        if namespace and not namespace.endswith("#"):
            namespace += "#"
        if not namespace and not experiment_id:
            logger.info("No URI, namespace or experiment_id provided")
            logger.info("Returning the list of experiments")
            return generate_response_with_all_experiments_in_json()
        logger.info(f"Requested the following experiment -> {namespace}{experiment_id}")
        if not namespace or not experiment_id:
            logger.info("Missing parameters: namespace or experiment_id")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing parameters: namespace or experiment_id"
            )
    try:
        json_ld_data = get_raw_graph_from_db() # Test if this is the correct way to get the data
        graph = utils.semantic.get_graph_from_json(json_ld_data)
        result_graph = utils.experiments.get_experiment_with_activities(graph, namespace, experiment_id)
        if len(result_graph) == 0:
            logger.info(f"Experiment not found: {namespace}{experiment_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment not found: {namespace}{experiment_id}"
            )
        logger.info("Experiment retrieved successfully")    
        response = PlainTextResponse(
            content=result_graph.serialize(format="turtle"),
            headers={
            "Content-Disposition": "attachment; filename=graph.ttl",
            "Content-Type": "text/turtle"
            },
            status_code=status.HTTP_200_OK
        )
        return response
    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Error retrieving experiment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving experiment: {str(e)}"
        )

def generate_response_with_all_experiments_in_json():
    '''
    Get the list of experiments from the graph.
    The response is a JSON file with the experiment URIs.
    The JSON file is generated using a SPARQL query.
    '''
    logger.info(f"Received request to get the list of experiments")
    try:
        json_ld_data = get_raw_graph_from_db()
        graph = utils.semantic.get_graph_from_json(json_ld_data)
        result = utils.experiments.get_experiment_list(graph)
        logger.debug(f"Experiment list as JSON: {result}")
        # Check if the bindings in the result are empty
        result_json = json.loads(result.decode('utf-8'))
        if len(result_json['results']['bindings']) == 0:
            logger.info("No experiments found")
            return PlainTextResponse(
                content="No experiments found",
                status_code=status.HTTP_204_NO_CONTENT)
        else:
            logger.info(f"Graph retrieved successfully. Returning the experiment list as JSON.")
            return JSONResponse(
                content=result_json,
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=experiments.json"},
                status_code=status.HTTP_200_OK
            )
    except HTTPException as e:
        logger.error(f"HTTPException: {e.detail}")
        raise e
    except Exception as e:
        logger.debug(f"Error retrieving experiment list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving experiment list: {str(e)}"
        )
        