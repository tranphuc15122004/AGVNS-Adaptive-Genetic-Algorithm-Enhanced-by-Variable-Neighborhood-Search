#include "graph.h"

#include <queue>
#include <limits>

struct GraphEdge
{
	int fromNode, toNode;
	GraphEdge* nextInEdge, *nextOutEdge;
	GraphEdge()
		: nextInEdge( NULL ), nextOutEdge( NULL ), fromNode( -1 ), toNode( -1 )
	{
	}
};

struct GraphNode
{
	GraphEdge *firstInEdge, *lastInEdge, *firstOutEdge, *lastOutEdge;
	int inDeg, outDeg;
	GraphNode()
		: firstInEdge( NULL ), firstOutEdge( NULL ), lastInEdge( NULL ), lastOutEdge( NULL ), inDeg( 0 ), outDeg( 0 )
	{
	}
};

Graph::Graph()
	: nNode( 0 ), nEdge( 0 ), edges( NULL ), nodes( NULL ), maxNodes( 0 ), maxEdges( 0 )
{
}

void Graph::clear()
{
	if( edges ) delete[] edges;
	if( nodes ) delete[] nodes;
	nNode = 0;
	nEdge = 0;
	edges = NULL;
	nodes = NULL;
}

void Graph::setSize( int maxNodes, int maxEdges )
{
	clear();

	this->maxEdges = maxEdges;
	this->maxNodes = maxNodes;
	nodes = new GraphNode[maxNodes];
	edges = new GraphEdge[maxEdges];
}

int Graph::addNode()
{
	if( nNode >= maxNodes ) throw;
	nodes[nNode].firstInEdge = NULL;  nodes[nNode].lastInEdge = NULL;
	nodes[nNode].firstOutEdge = NULL;  nodes[nNode].lastOutEdge = NULL;
	nodes[nNode].inDeg = 0; nodes[nNode].outDeg = 0;
	return nNode++;
}

int Graph::addEdge( int fromNode, int toNode )
{
	if( nEdge >= maxEdges ) throw;
	GraphEdge *pEdge = edges + nEdge;
	pEdge->fromNode = fromNode;
	pEdge->toNode = toNode;
	pEdge->nextInEdge = NULL;
	pEdge->nextOutEdge = NULL;
	if( nodes[fromNode].lastOutEdge != NULL ) {
		nodes[fromNode].lastOutEdge->nextOutEdge = pEdge;
		nodes[fromNode].lastOutEdge = pEdge;
	}
	else {
		nodes[fromNode].firstOutEdge = pEdge;
		nodes[fromNode].lastOutEdge = pEdge;
	}
	nodes[fromNode].outDeg++;

	if( nodes[toNode].lastInEdge != NULL ) {
		nodes[toNode].lastInEdge->nextInEdge = pEdge;
		nodes[toNode].lastInEdge = pEdge;
	}
	else {
		nodes[toNode].firstInEdge = pEdge;
		nodes[toNode].lastInEdge = pEdge;
	}
	nodes[toNode].inDeg++;

	return nEdge++;
}

int Graph::getNodeNum() const
{
	return nNode;
}

int Graph::getEdgeNum() const
{
	return nEdge;
}

int Graph::getInDeg( int n ) const {
	return nodes[n].inDeg;
}

int Graph::getOutDeg( int n ) const {
	return nodes[n].outDeg;
}

int Graph::getFromNode( int edgeIdx ) const
{
	return edges[edgeIdx].fromNode;
}

int Graph::getToNode( int edgeIdx ) const
{
	return edges[edgeIdx].toNode;
}

std::ostream & operator<<( std::ostream &os, const Graph& g )
{
	os << "[nodes: " << g.nNode << ", edges: " << g.nEdge << "\n";
	for( int n = 0; n < g.nNode; ++n ) {
		GraphNode &node = g.nodes[n];
		os << "\t{n#" << n << ", indeg: " << node.inDeg << ", outdeg: " << node.outDeg << " in edges: {";
		for( GraphInEdgeIterator it( g, n ); !it.atEnd(); ++it ) {
			GraphEdge &edge = g.edges[*it];
			os << '(' << edge.fromNode << "," << edge.toNode << ')';
		}
		os << "}, out edges: {";
		for( GraphOutEdgeIterator it( g, n ); !it.atEnd(); ++it ) {
			GraphEdge &edge = g.edges[*it];
			os << '(' << edge.fromNode << "," << edge.toNode << ')';
		}
		os << "}}\n";
	}
	os << ']';
	return os;
}

GraphInEdgeIterator::GraphInEdgeIterator( const Graph &g, int node )
	: next( g.nodes[node].firstInEdge ), graph( g )
{

}

inline int GraphInEdgeIterator::edgeIndex() const {
	if( next != NULL )
		return next - graph.edges;
	else
		return -1;
}

inline bool GraphInEdgeIterator::atEnd() const
{
	return next == NULL;
}

int operator *( const GraphInEdgeIterator &it )
{
	return it.edgeIndex();
}

GraphInEdgeIterator & operator ++( GraphInEdgeIterator &it )
{
	if( it.next != NULL ) {
		it.next = it.next->nextInEdge;
	}
	return it;
}

GraphOutEdgeIterator::GraphOutEdgeIterator( const Graph &g, int node )
	: next( g.nodes[node].firstOutEdge ), graph( g )
{

}

inline int GraphOutEdgeIterator::edgeIndex() const {
	if( next != NULL )
		return next - graph.edges;
	else
		return -1;
}

inline bool GraphOutEdgeIterator::atEnd() const
{
	return next == NULL;
}

int operator *( const GraphOutEdgeIterator &it )
{
	return it.edgeIndex();
}

GraphOutEdgeIterator & operator ++( GraphOutEdgeIterator &it )
{
	if( it.next != NULL ) {
		it.next = it.next->nextOutEdge;
	}
	return it;
}

#define INF std::numeric_limits<double>::max()

// iPair ==>  Integer Pair
typedef std::pair<double, int> iPair;

// Prints shortest paths from src to all other vertices
void Graph::shortestPaths( int src, const double *cost, double *dist, int *backPtr )
{
	// Create a priority queue to store vertices that
	// are being preprocessed.
	std::priority_queue< iPair, std::vector <iPair>, std::greater<iPair> > pq;

	// set all distances INF
	for( int n = 0; n < nNode; ++n ) dist[n] = INF;

	// Insert source itself in priority queue and initialize
	// its distance as 0.
	pq.push( std::make_pair( 0, src ) );
	dist[src] = 0;

	/* Looping till priority queue becomes empty (or all
		distances are not finalized) */
	while( !pq.empty() )
	{
		// The first vertex in pair is the minimum distance
		// vertex, extract it from priority queue.
		// vertex label is stored in second of pair (it
		// has to be done this way to keep the vertices
		// sorted distance (distance must be first item
		// in pair)
		int u = pq.top().second;
		pq.pop();

		// 'i' is used to get all adjacent vertices of a vertex

		for( GraphOutEdgeIterator i( *this, u ); !i.atEnd(); ++i )
		{
			// Get vertex label and weight of current adjacent
			// of u.
			int e = *i;
			int v = edges[e].toNode;
			double weight = cost[e];

			//  If there is shorted path to v through u.
			if( dist[v] > dist[u] + weight )
			{
				// Updating distance of v
				dist[v] = dist[u] + weight;
				pq.push( std::make_pair( dist[v], v ) );
				if( backPtr ) backPtr[v] = u;
			}
		}
	}
}
