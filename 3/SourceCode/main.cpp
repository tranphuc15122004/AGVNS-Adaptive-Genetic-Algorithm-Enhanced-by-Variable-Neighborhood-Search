#include <stdio.h>
#include <limits>
#include <thread>

#include "config.h"
#include "dpdp.h"
#include "inputdata.h"
#include "probdata.h"
#include "timer.h"

#ifdef DPDP_DEMO_SOLVER
#include "demo_solver.h"
#else
#include "lssolver.h"
#endif

int run()
{
	InputData inputdata;
	DPDP_CALL( inputdata.readStaticData( FACTORY_INFO_FILE, ROUTEMAP_FILE ) );
	DPDP_CALL( inputdata.readInteractionData( VEHICLE_INFO_FILE, ONGOING_ORDER_ITEMS_INFO_FILE, UNALLOCATED_ORDER_ITEMS_FILE ) );

	ProbData probdata;
	DPDP_CALL( probdata.build( inputdata, ROUTEMAP_FILE ) );

#ifdef DPDP_DEMO_SOLVER
	DemoSolver solver;
	DPDP_CALL( solver.init( &probdata ) );
	DPDP_CALL( solver.run() );
#else
	LocalSearchSolver solver( &probdata );
	DPDP_CALL( solver.run() );
#endif

	return 0;
}

int processArguments( int argc, char* argv[] )
{
	if( argc >= 2 )
		FACTORY_INFO_FILE = argv[1];

	if( argc >= 3 )
		ROUTEMAP_FILE = argv[2];

	if( argc >= 4 )
		VEHICLE_INFO_FILE = argv[3];

	if( argc >= 5 )
		ONGOING_ORDER_ITEMS_INFO_FILE = argv[4];

	if( argc >= 6 )
		UNALLOCATED_ORDER_ITEMS_FILE = argv[5];

	if( argc >= 7 )
		OUTPUT_ROUTE_FILE = argv[6];

	if( argc >= 8 )
		OUTPUT_DESTINATION_FILE = argv[7];

	if( argc >= 9 )
		LOAD_SPEED = atof( argv[8] );

	if( argc >= 10 )
		UNLOAD_SPEED = atof( argv[9] );

	if( argc >= 11 )
		DOCK_APPROACHING_TIME = atoi( argv[10] );

	if( argc >= 12 )
		CONFIG_LAMBDA = atoi( argv[11] );

	dpdpPrintfDebug( "load speed: %f\n", LOAD_SPEED );
	dpdpPrintfDebug( "unload speed: %f\n", UNLOAD_SPEED );
	dpdpPrintfDebug( "dock approaching time: %d\n", DOCK_APPROACHING_TIME );
	dpdpPrintfDebug( "lambda: %d\n", CONFIG_LAMBDA );

	return 0;
}

int main( int argc, char* argv[] )
{
#ifdef _MSC_VER
#ifdef _DEBUG
	int flag = _CrtSetDbgFlag(_CRTDBG_REPORT_FLAG);
	flag |= _CRTDBG_LEAK_CHECK_DF | _CRTDBG_CHECK_EVERY_16_DF | _CRTDBG_CHECK_CRT_DF | _CRTDBG_ALLOC_MEM_DF; // Turn on leak-checking bit // _CRTDBG_CHECK_ALWAYS_DF, _CRTDBG_CHECK_EVERY_16_DF
	_CrtSetDbgFlag(flag);

	//_CrtSetBreakAlloc( 239640 );
#endif
#endif

	GlobalTimer::getInstance().start(); // starts global timer

	std::this_thread::sleep_for( std::chrono::milliseconds(1) );

	//printf( "RUN...\n" );

	DPDP_CALL( processArguments( argc, argv ) );
	DPDP_CALL( run() );

	printf( "SUCCESS\n" );

	std::this_thread::sleep_for( std::chrono::milliseconds( 1 ) );

	return 0;
}
