#ifndef _DPDP_GRAPH_H_
#define _DPDP_GRAPH_H_

#include <stdlib.h>
#include <ostream>

struct GraphEdge;
struct GraphNode;

class Graph
{
	friend class GraphInEdgeIterator;
	friend class GraphOutEdgeIterator;
	friend std::ostream & operator<<( std::ostream &, const Graph& );

protected:
	int nNode;
	int nEdge;
	int maxNodes;
	int maxEdges;
	GraphEdge *edges;
	GraphNode *nodes;

public:
	Graph();
	~Graph()
	{
		clear();
	}
	void clear();

	void setSize( int maxNodes, int maxEdges );

	int addNode();
	int addEdge( int fromNode, int toNode );

	void shortestPaths( int srcNode, const double *cost, double *dist, int *backPtr );

	int getNodeNum() const;
	int getEdgeNum() const;

	int getInDeg( int nodeId ) const;
	int getOutDeg( int nodeId ) const;

	int getFromNode( int edgeId ) const;
	int getToNode( int edgeId ) const;
};

std::ostream & operator<<( std::ostream &, const Graph& );

class GraphInEdgeIterator
{
	friend int operator *( const GraphInEdgeIterator & );
	friend GraphInEdgeIterator & operator ++( GraphInEdgeIterator & );
	const GraphEdge *next;
	const Graph &graph;
public:
	GraphInEdgeIterator( const Graph &g, int node );

	inline int edgeIndex() const;
	inline bool atEnd() const;
};

int operator *( const GraphInEdgeIterator &it );
GraphInEdgeIterator & operator ++( GraphInEdgeIterator &it );

class GraphOutEdgeIterator
{
	friend int operator *( const GraphOutEdgeIterator & );
	friend GraphOutEdgeIterator & operator ++( GraphOutEdgeIterator & );
	const GraphEdge *next;
	const Graph &graph;

public:
	GraphOutEdgeIterator( const Graph &g, int node );
	inline int edgeIndex() const;
	inline bool atEnd() const;
};

int operator *( const GraphOutEdgeIterator &it );
GraphOutEdgeIterator & operator ++( GraphOutEdgeIterator &it );

#endif
