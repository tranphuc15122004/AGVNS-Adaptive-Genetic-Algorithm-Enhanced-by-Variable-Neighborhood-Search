OBJDIR = objdir
OBJS = $(addprefix $(OBJDIR)/, main.o probdata.o graph.o lssolver.o scheduler.o inputdata.o demo_solver.o config.o binpacking.o statistics.o pd.o pd_ls.o)
CXX = g++
CPPFLAGS =-O3
CXXFLAGS =-DDPDP_DEBUG


main_algorithm.out : $(OBJS)
	$(CXX) $(OUTPUT_OPTION) $(OBJS)

.cpp.o:
	$(CXX) $(CPPFLAGS) $(INCLUDES) -c $<  -o $@

$(OBJDIR)/main.o : main.cpp dpdp.h inputdata.h probdata.h lssolver.h config.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c main.cpp -o $(OBJDIR)/main.o

$(OBJDIR)/lssolver.o : lssolver.cpp lssolver.h probdata.h solverdata.h dpdp.h config.h scheduler.h solution.h lssolver_compaux.h timer.h binpacking.h statistics.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c lssolver.cpp -o $(OBJDIR)/lssolver.o

$(OBJDIR)/probdata.o : probdata.cpp probdata.h dpdp.h inputdata.h graph.h dpdp.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c probdata.cpp -o $(OBJDIR)/probdata.o

$(OBJDIR)/demo_solver.o : demo_solver.cpp demo_solver.h probdata.h config.h dpdp.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c demo_solver.cpp -o $(OBJDIR)/demo_solver.o

$(OBJDIR)/graph.o : graph.cpp graph.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c graph.cpp -o $(OBJDIR)/graph.o

$(OBJDIR)/inputdata.o : inputdata.cpp inputdata.h dpdp.h rapidjson/document.h rapidjson/filereadstream.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c inputdata.cpp -o $(OBJDIR)/inputdata.o

$(OBJDIR)/config.o : config.cpp config.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c config.cpp -o $(OBJDIR)/config.o

$(OBJDIR)/scheduler.o: scheduler.h scheduler.cpp solution_aux.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c scheduler.cpp -o $(OBJDIR)/scheduler.o

$(OBJDIR)/binpacking.o: binpacking.h binpacking.cpp solution_aux.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c binpacking.cpp -o $(OBJDIR)/binpacking.o

$(OBJDIR)/statistics.o: statistics.h statistics.cpp probdata.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c statistics.cpp -o $(OBJDIR)/statistics.o

$(OBJDIR)/pd.o: pd.h pd.cpp probdata.h scheduler.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c pd.cpp -o $(OBJDIR)/pd.o

$(OBJDIR)/pd_ls.o: pd_ls.h pd_ls.cpp probdata.h scheduler.h
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c pd_ls.cpp -o $(OBJDIR)/pd_ls.o


.PHONY : clean
clean :
	rm $(OBJDIR)/*

$(OBJS): | $(OBJDIR)

$(OBJDIR):
	mkdir $(OBJDIR)
