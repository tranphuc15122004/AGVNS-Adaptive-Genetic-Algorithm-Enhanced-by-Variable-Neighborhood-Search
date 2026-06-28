#pragma once
#include "probdata.h"
#include "scheduler.h"
struct Statistics
{
	const ProbData& probdata;
	int num_factories;
	int num_vehicles;
	double** node_to_node_demand; // matrix of size num_factories x num_factories
	double* total_pickup; // array of size num_factories
	double* total_delivery;  // array of size num_factories
	int *visiting_vehicles; // array of size num_factories
	Statistics(const ProbData& _probdata);
	~Statistics();

	void compute();

	void writeStatistics();

	// counts the number of vehicles visiting each factory 
	void count_visiting_vehicles(Scheduler& sch);

	void write_schedule_stats(Scheduler& sch);
};

