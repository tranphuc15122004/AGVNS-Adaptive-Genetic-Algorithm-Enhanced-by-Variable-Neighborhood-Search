#pragma once

#include "dpdp.h"

#include <list>

class PD;
struct Package;
struct PDNode;
class ProbData;
class Timer;

class PDMovement
{
public:
	double evaluated_value; // evaluated value after movement is applied

public:
	virtual void apply( PD* parent ) = 0; // apply movement
	virtual void undo( PD* parent ) = 0;  // undo movement
	void applyWithEvaluation( PD* parent );

protected:
	PDMovement() : evaluated_value( std::numeric_limits<double>::max() )
	{
	}
};

class PDSimpleRemoval : public PDMovement
{
public:
	const Package* package; // package to remove
	bool component;         // indicates whether the whole component must be moved

private:
	int from_vehicle;           // original vehicle
	PDNode* from_pickup_pred;   // original predecessor of pickup node
	PDNode* from_delivery_succ; // original successor of delivery node

public:
	void copy_to( PDSimpleRemoval*& copy );

public:
	void apply( PD* parent ); // remove package/component from schedule
	void undo( PD* parent );  // insert back package/component to its original place

public:
	PDSimpleRemoval() : PDMovement(),
		package( NULL ), component( false ),
		from_vehicle( -1 ), from_pickup_pred( NULL ), from_delivery_succ( NULL )
	{
	}
};

class PDSimpleInsertion : public PDMovement
{
public:
	const Package* package;   // package to insert
	bool component;           // indicates whether the whole component must be inserted

public:
	int to_vehicle;           // vehicle to insert to
	PDNode* to_pickup_pred;   // future predecessor of pickup node (insert after)
	PDNode* to_delivery_succ; // future successor of delivery node (insert before)

public:
	void apply( PD* parent ); // remove package/component from schedule
	void undo( PD* parent );  // insert back package/component into its original place

public:
	void copy_to( PDSimpleInsertion*& copy );

public:
	PDSimpleInsertion() : PDMovement(),
		package( NULL ), component( false ), to_vehicle( -1 ), to_pickup_pred( NULL ), to_delivery_succ( NULL )
	{
	}
};

typedef std::pair<PDNode*, PDNode*> PDNodePair;

class PDGroupRemoval : public PDMovement
{
public:
	PDNodePair first_interval;
	PDNodePair second_interval;

private:
	PDNode* from_pred_first;
	PDNode* from_succ_second;
	int from_vehicle;

public:
	void apply( PD* parent );
	void undo( PD* parent );

public:
	void copy_to( PDGroupRemoval*& copy );

public:
	PDGroupRemoval() : PDMovement(), from_pred_first( NULL ), from_succ_second( NULL ), from_vehicle( -1 )
	{
	}
};

class PDGroupInsertion : public PDMovement
{
public:
	PDNodePair first_interval;
	PDNodePair second_interval;
	PDNode* to_pred_first;
	PDNode* to_succ_second;
	int to_vehicle;

public:
	void apply( PD* parent );
	void undo( PD* parent );

public:
	void copy_to( PDGroupInsertion*& copy );

public:
	PDGroupInsertion() : PDMovement(), to_pred_first( NULL ), to_succ_second( NULL ), to_vehicle( -1 )
	{
	}
};

class PDSimpleTransfer : public PDMovement
{
public:
	PDSimpleRemoval removal;
	PDSimpleInsertion insertion;

public:
	void apply( PD* parent ); // apply removal and insertion
	void undo( PD* parent );  // undo insertion and removal

public:
	PDSimpleTransfer() : PDMovement()
	{
	}
};

class PDGroupTransfer : public PDMovement
{
public:
	PDGroupRemoval removal;
	PDGroupInsertion insertion;

public:
	void apply( PD* parent ); // apply removal and insertion
	void undo( PD* parent );  // undo insertion and removal

public:
	PDGroupTransfer() : PDMovement()
	{
	}
};

class PDLocalSearch
{
private:
	PD* parent;
	const ProbData* probdata;

private:
	double actual_value; // current value of parent schedule

public:
	PDLocalSearch( PD* _parent, const ProbData* _probdata );

public:
	bool run( long long time_limit );

private:
	bool stepToBestNeighbor( const Timer& timer );

private: // main methods to call inside local search
	PDSimpleTransfer* findBestTransfer( const bool component );
	PDGroupTransfer* findBestGroupTransfer();

private: // main sub-methods
	PDGroupInsertion* findBestInsertationOfPackageOnVehicle(PDNode* pickup_node_first, PDNode* pickup_node_last, PDNode* delivery_node_first, PDNode* delivery_node_last, const int to_vehicle );
	
	PDSimpleInsertion* findBestInsertationOfComponentOnVehicle( PDNode* pickup_node, PDNode* delivery_node, const int to_vehicle );

	PDSimpleInsertion* findBestInsertationOnVehicle( PDNode* pickup_node, PDNode* delivery_node, const int to_vehicle, const bool component )
	{
		if( component )
			return findBestInsertationOfComponentOnVehicle( pickup_node, delivery_node, to_vehicle );
		else
			DPDP_ASSERT_ABORT( false ); //return findBestInsertationOfPackageOnVehicle( pickup_node, delivery_node, to_vehicle );
	}

private: // dummy sub-methods
	PDSimpleInsertion* findBestInsertation( PDNode* pickup_node, PDNode* delivery_node, const bool component );
	PDSimpleInsertion* findBestInsertation( const Package* package, const bool component );
};
